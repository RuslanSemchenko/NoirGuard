import hmac
import hashlib
import os
from typing import Annotated
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException, Header
from app.agent import QwenClient
from app.validator import Validator
from app.github_client import GitHubClient
from app.orchestrator import RemediationOrchestrator

app = FastAPI(title="NoirGuard API")

# Initialize components
agent = QwenClient()
validator = Validator()
github = GitHubClient()
orchestrator = RemediationOrchestrator(agent, validator)

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "super-secret").encode()

@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "NoirGuard API is running."}

async def verify_signature(
    request: Request,
    x_hub_signature_256: Annotated[str, Header(None)]
) -> None:
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")

    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "super-secret").encode()
    payload = await request.body()

    expected_signature = "sha256=" + hmac.new(secret, payload,
                                              hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid signature")

async def process_remediation(repo: str, issue_number: int,
                              code: str, report: str) -> None:
    patch = await orchestrator.remediate(code, report)
    github.comment_on_issue(repo, issue_number, f"NoirGuard remediation:\n\n{patch}")

@app.post(
    "/webhook",
    responses={
        401: {"description": "Missing signature"},
        403: {"description": "Invalid signature"}
    }
)
async def github_webhook(
    request: Request,
    background_tasks: Annotated[BackgroundTasks, BackgroundTasks()],
    signature: Annotated[str, Header(..., alias="X-Hub-Signature-256")]
) -> dict[str, str]:
    await verify_signature(request, signature)
    payload = await request.json()

    # Simplified webhook processing logic
    repo = payload.get("repository", {}).get("full_name", "")
    issue_number = payload.get("issue", {}).get("number", 0)

    if repo and issue_number:
        # Trigger remediation in the background
        background_tasks.add_task(process_remediation, repo, issue_number,
                                  "<code>", "Report")
        return {"status": "remediation triggered"}

    return {"status": "no action taken"}
