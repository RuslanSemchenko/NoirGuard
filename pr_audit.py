import asyncio
import sys
import os
import httpx
from app.agent import QwenClient
from app.validator import Validator
from app.orchestrator import RemediationOrchestrator
from app.github_client import GitHubClient


async def fetch_pr_code(repo: str, pr_number: int, token: str) -> tuple[str, str]:
    pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
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
    for f in files:
        filename = f.get("filename", "")
        patch = f.get("patch", "")
        if filename.endswith(".py"):
            status = f.get("status", "modified")
            code_parts.append(f"# File: {filename} ({status})\n{patch}")

    combined = "\n\n".join(code_parts) if code_parts else "No Python files changed."
    report = f"PR #{pr_number}: {title}\n\n{body or 'No description'}"
    return combined, report


def post_comment(repo: str, pr_number: int, comment: str) -> None:
    github = GitHubClient()
    pr_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    import json
    headers = {
        "Authorization": f"token {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    data = json.dumps({"body": comment})
    import urllib.request
    req = urllib.request.Request(pr_url, data=data.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


async def main():
    token = os.getenv("GITHUB_TOKEN")
    qwen_key = os.getenv("QWEN_API_KEY")
    if not token:
        print("[!] GITHUB_TOKEN not set"); sys.exit(1)
    if not qwen_key:
        print("[!] QWEN_API_KEY not set"); sys.exit(1)

    if len(sys.argv) < 3:
        print("Usage: python pr_audit.py <repo> <pr_number>")
        print("Example: python pr_audit.py RuslanSemchenko/NoirGuard 1")
        sys.exit(1)

    repo = sys.argv[1]
    pr_number = int(sys.argv[2])

    print(f"NoirGuard PR Audit")
    print("=" * 50)
    print(f"\n[*] Fetching PR #{pr_number} from {repo}...")
    code, report = await fetch_pr_code(repo, pr_number, token)
    print(f"[*] Found {len(code)} chars of code changes")

    agent = QwenClient()
    validator = Validator()
    orchestrator = RemediationOrchestrator(agent, validator)

    print("[*] Running initial validation (pylint + snyk)...")
    with __import__("tempfile").NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code if len(code) < 100000 else code[:100000])
        tmp = f.name
    result = validator.run_validation(tmp)
    os.unlink(tmp)
    print(f"  Pylint: {'OK' if not (result['pylint_log'] and 'error' in result['pylint_log'].lower()) else 'ISSUES'}")
    print(f"  Snyk:   {'OK' if not (result['snyk_log'] and ('issue' in result['snyk_log'].lower() or 'error' in result['snyk_log'].lower())) else 'ISSUES'}")

    print(f"\n[*] Sending to Qwen API for remediation...")
    patch = await orchestrator.remediate(code[:8000], "Code from PR #{pr_number}")

    print(f"\n[+] Remediation result:")
    print(patch[:500])

    print(f"\n[*] Posting comment to PR #{pr_number}...")
    comment = (f"## NoirGuard Remediation Report\n\n"
               f"{patch}\n\n"
               f"_Automated audit complete._")
    try:
        post_comment(repo, pr_number, comment)
        print(f"[+] Comment posted: https://github.com/{repo}/pull/{pr_number}")
    except Exception as e:
        print(f"[!] Failed to post comment: {e}")
        print(f"\n--- Comment content ---\n{comment}")

    print("=" * 50)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
