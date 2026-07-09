"""CLI: fetch a GitHub PR diff, audit it with NoirGuard and post the patch back."""

import asyncio
import os
import sys
import tempfile

import httpx
from github import GithubException

from app.agent import QwenClient
from app.github_client import GitHubClient
from app.orchestrator import RemediationOrchestrator
from app.scanner import SecurityScanner
from app.validator import Validator

MAX_CODE_CHARS = 100_000
MAX_PROMPT_CHARS = 8_000


async def fetch_pr_code(repo: str, pr_number: int, token: str) -> tuple[str, str]:
    """Fetch the Python file patches and metadata for a pull request."""
    pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient() as client:
        pr_resp = await client.get(pr_url, headers=headers)
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()
        title = pr_data.get("title", "")
        body = pr_data.get("body", "")

        files_resp = await client.get(f"{pr_url}/files", headers=headers)
        files_resp.raise_for_status()
        files = files_resp.json()

    code_parts = []
    for changed_file in files:
        filename = changed_file.get("filename", "")
        patch = changed_file.get("patch", "")
        if filename.endswith(".py"):
            status = changed_file.get("status", "modified")
            code_parts.append(f"# File: {filename} ({status})\n{patch}")

    combined = "\n\n".join(code_parts) if code_parts else "No Python files changed."
    report = f"PR #{pr_number}: {title}\n\n{body or 'No description'}"
    return combined, report


def run_initial_validation(validator: Validator, code: str) -> None:
    """Run pylint/snyk on the raw PR code and print a short summary."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as tmp_file:
        tmp_file.write(code[:MAX_CODE_CHARS])
        tmp_path = tmp_file.name
    try:
        result = validator.run_validation(tmp_path)
    finally:
        os.unlink(tmp_path)

    pylint_ok = not (
        result["pylint_log"] and "error" in result["pylint_log"].lower()
    )
    snyk_ok = not (
        result["snyk_log"]
        and ("issue" in result["snyk_log"].lower() or "error" in result["snyk_log"].lower())
    )
    print(f"  Pylint: {'OK' if pylint_ok else 'ISSUES'}")
    print(f"  Snyk:   {'OK' if snyk_ok else 'ISSUES'}")


def print_scan_summary(code: str) -> None:
    """Run the local static scanner on the PR code and print the findings."""
    report = SecurityScanner().scan(code)
    print("[*] Local static scan:")
    print("  " + report.summary().replace("\n", "\n  "))


def parse_args(argv: list[str]) -> tuple[str, int]:
    """Parse and validate CLI arguments, exiting with usage help on error."""
    if len(argv) < 3:
        print("Usage: python pr_audit.py <repo> <pr_number>")
        print("Example: python pr_audit.py RuslanSemchenko/NoirGuard 1")
        sys.exit(1)
    try:
        return argv[1], int(argv[2])
    except ValueError:
        print("[!] pr_number must be an integer")
        sys.exit(1)


def require_env(name: str) -> str:
    """Return an environment variable or exit with an error message."""
    value = os.getenv(name)
    if not value:
        print(f"[!] {name} not set")
        sys.exit(1)
    return value


async def main() -> None:
    """Entry point: audit a PR and post the remediation as a comment."""
    token = require_env("GITHUB_TOKEN")
    require_env("QWEN_API_KEY")

    repo, pr_number = parse_args(sys.argv)

    print("NoirGuard PR Audit")
    print("=" * 50)
    print(f"\n[*] Fetching PR #{pr_number} from {repo}...")
    code, report = await fetch_pr_code(repo, pr_number, token)
    print(f"[*] Found {len(code)} chars of code changes")

    validator = Validator()
    orchestrator = RemediationOrchestrator(QwenClient(), validator)

    print("[*] Running initial validation (pylint + snyk)...")
    run_initial_validation(validator, code)
    print_scan_summary(code)

    print("\n[*] Sending to Qwen API for remediation...")
    patch = await orchestrator.remediate(code[:MAX_PROMPT_CHARS], report)

    print("\n[+] Remediation result:")
    print(patch[:500])

    print(f"\n[*] Posting comment to PR #{pr_number}...")
    comment = (
        "## NoirGuard Remediation Report\n\n"
        f"{patch}\n\n"
        "_Automated audit complete._"
    )
    try:
        GitHubClient(token).comment_on_issue(repo, pr_number, comment)
        print(f"[+] Comment posted: https://github.com/{repo}/pull/{pr_number}")
    except (ValueError, OSError, GithubException) as exc:
        print(f"[!] Failed to post comment: {exc}")
        print(f"\n--- Comment content ---\n{comment}")

    print("=" * 50)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
