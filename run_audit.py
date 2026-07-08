import asyncio
import sys
import os
from app.agent import QwenClient
from app.validator import Validator
from app.orchestrator import RemediationOrchestrator

VULNERABLE_CODE = """import os

def get_file(path):
    return open(path).read()

def run(cmd):
    os.system(cmd)

def unsafe_eval(data):
    eval(data)
"""

async def main():
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        print("[!] QWEN_API_KEY not set")
        sys.exit(1)

    print("NoirGuard Audit")
    print("=" * 40)
    print("\n[*] Checking target code...\n")
    print(VULNERABLE_CODE)

    agent = QwenClient()
    validator = Validator()
    orchestrator = RemediationOrchestrator(agent, validator)

    print("[*] Running local validation (pylint + snyk)...")
    with __import__("tempfile").NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(VULNERABLE_CODE)
        tmp = f.name
    result = validator.run_validation(tmp)
    os.unlink(tmp)

    pylint_ok = not (result['pylint_log'] and 'error' in result['pylint_log'].lower())
    snyk_ok = not (result['snyk_log'] and ('issue' in result['snyk_log'].lower() or 'error' in result['snyk_log'].lower()))
    print(f"\n  Pylint: {'OK' if pylint_ok else 'ISSUES'}")
    if result['pylint_log']:
        print(f"  Log: {result['pylint_log'][:200]}")
    print(f"  Snyk:   {'OK' if snyk_ok else 'ISSUES'}")
    if result['snyk_log']:
        print(f"  Log: {result['snyk_log'][:200]}")

    print("\n[*] Sending to Qwen API for remediation...")
    patch = await orchestrator.remediate(VULNERABLE_CODE, "Path Traversal, Command Injection, Code Injection")

    print("\n[+] Remediation result:\n")
    print(patch)
    print("=" * 40)

if __name__ == "__main__":
    asyncio.run(main())
