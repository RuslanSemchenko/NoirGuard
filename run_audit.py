"""CLI: run a local NoirGuard audit against a built-in vulnerable code sample."""

import asyncio
import os
import sys
import tempfile

from app.agent import QwenClient
from app.orchestrator import RemediationOrchestrator
from app.scanner import SecurityScanner
from app.validator import Validator

VULNERABLE_CODE = """import os

def get_file(path):
    return open(path).read()

def run(cmd):
    os.system(cmd)

def unsafe_eval(data):
    eval(data)
"""


def run_local_validation(validator: Validator, code: str) -> None:
    """Validate the sample code with pylint/snyk and print a summary."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as tmp_file:
        tmp_file.write(code)
        tmp_path = tmp_file.name
    try:
        result = validator.run_validation(tmp_path)
    finally:
        os.unlink(tmp_path)

    pylint_ok = not (
        result["pylint_log"] and "error" in result["pylint_log"].lower()
    )
    snyk_log = result["snyk_log"]
    snyk_ok = not (
        snyk_log and ("issue" in snyk_log.lower() or "error" in snyk_log.lower())
    )
    print(f"\n  Pylint: {'OK' if pylint_ok else 'ISSUES'}")
    if result["pylint_log"]:
        print(f"  Log: {result['pylint_log'][:200]}")
    print(f"  Snyk:   {'OK' if snyk_ok else 'ISSUES'}")
    if snyk_log:
        print(f"  Log: {snyk_log[:200]}")


async def main() -> None:
    """Entry point: validate, scan and remediate the vulnerable sample."""
    if not os.getenv("QWEN_API_KEY"):
        print("[!] QWEN_API_KEY not set")
        sys.exit(1)

    print("NoirGuard Audit")
    print("=" * 40)
    print("\n[*] Checking target code...\n")
    print(VULNERABLE_CODE)

    validator = Validator()
    orchestrator = RemediationOrchestrator(QwenClient(), validator)

    print("[*] Running local validation (pylint + snyk)...")
    run_local_validation(validator, VULNERABLE_CODE)

    print("\n[*] Local static scan:")
    print(SecurityScanner().scan(VULNERABLE_CODE).summary())

    print("\n[*] Sending to Qwen API for remediation...")
    patch = await orchestrator.remediate(
        VULNERABLE_CODE, "Path Traversal, Command Injection, Code Injection"
    )

    print("\n[+] Remediation result:\n")
    print(patch)
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(main())
