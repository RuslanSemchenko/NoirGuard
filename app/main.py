"""NoirGuard FastAPI application: webhook intake, scanning and remediation."""

import hashlib
import hmac
import os
from functools import lru_cache
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.agent import QwenClient
from app.github_client import GitHubClient
from app.orchestrator import RemediationOrchestrator
from app.scanner import SecurityScanner
from app.validator import Validator

app = FastAPI(title="NoirGuard API")

scanner = SecurityScanner()


@lru_cache(maxsize=1)
def get_orchestrator() -> RemediationOrchestrator:
    """Lazily build the orchestrator so imports work without env vars."""
    return RemediationOrchestrator(QwenClient(), Validator(), scanner)


@lru_cache(maxsize=1)
def get_github() -> GitHubClient:
    """Lazily build the GitHub client so imports work without env vars."""
    return GitHubClient()


class ScanRequest(BaseModel):
    """Request body for the /scan endpoint."""

    code: str = Field(..., min_length=1, description="Python source code to scan")


@app.get("/")
async def root() -> dict[str, str]:
    """Basic service banner."""
    return {"message": "NoirGuard API is running."}


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.post("/scan")
async def scan_code(payload: ScanRequest) -> dict[str, Any]:
    """Run the local static security scanner against submitted code."""
    report = scanner.scan(payload.code)
    return report.to_dict()


async def verify_signature(request: Request, signature: str | None) -> None:
    """Validate the GitHub webhook HMAC signature against the shared secret."""
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "super-secret").encode()
    payload = await request.body()

    expected_signature = (
        "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    )

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")


def parse_webhook_target(payload: dict[str, Any]) -> tuple[str, int]:
    """Extract the repository name and issue/PR number from a webhook payload."""
    repo = payload.get("repository", {}).get("full_name", "")
    number = (
        payload.get("pull_request", {}).get("number")
        or payload.get("issue", {}).get("number")
        or 0
    )
    return repo, int(number)


async def process_remediation(
    repo: str, issue_number: int, code: str, report: str
) -> None:
    """Background task: remediate code and post the result as a comment."""
    patch = await get_orchestrator().remediate(code, report)
    get_github().comment_on_issue(
        repo, issue_number, f"NoirGuard remediation:\n\n{patch}"
    )


@app.post(
    "/webhook",
    responses={
        401: {"description": "Missing signature"},
        403: {"description": "Invalid signature"},
    },
)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """GitHub webhook entrypoint: verifies the signature and queues remediation."""
    await verify_signature(request, x_hub_signature_256)
    payload = await request.json()

    repo, issue_number = parse_webhook_target(payload)

    if repo and issue_number:
        background_tasks.add_task(
            process_remediation, repo, issue_number, "<code>", "Report"
        )
        return {"status": "remediation triggered"}

    return {"status": "no action taken"}
