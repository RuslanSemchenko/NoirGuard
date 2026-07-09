"""Tests for the FastAPI application endpoints."""

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.main import app, parse_webhook_target

client = TestClient(app)

SECRET = b"super-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()


def test_root():
    """The root endpoint returns the service banner."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "NoirGuard API is running."}


def test_health():
    """The health endpoint reports ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_scan_clean_code():
    """Scanning safe code returns passed=True."""
    response = client.post("/scan", json={"code": "x = 1"})
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["finding_count"] == 0


def test_scan_vulnerable_code():
    """Scanning dangerous code returns findings."""
    response = client.post("/scan", json={"code": "eval(x)"})
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["findings"][0]["rule"] == "CODE_INJECTION"


def test_scan_empty_code_rejected():
    """An empty code payload fails validation."""
    response = client.post("/scan", json={"code": ""})
    assert response.status_code == 422


def test_webhook_missing_signature():
    """A webhook without a signature is rejected with 401."""
    response = client.post("/webhook", json={})
    assert response.status_code == 401


def test_webhook_invalid_signature():
    """A webhook with a wrong signature is rejected with 403."""
    response = client.post(
        "/webhook",
        content=b"{}",
        headers={
            "X-Hub-Signature-256": "sha256=deadbeef",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403


def test_webhook_valid_signature_no_target():
    """A valid signature with no repo/issue takes no action."""
    body = json.dumps({}).encode()
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "no action taken"}


def test_parse_webhook_target_pull_request():
    """PR payloads take precedence when extracting the target number."""
    payload = {
        "repository": {"full_name": "org/repo"},
        "pull_request": {"number": 7},
        "issue": {"number": 3},
    }
    assert parse_webhook_target(payload) == ("org/repo", 7)


def test_parse_webhook_target_issue_fallback():
    """Issue payloads are used when no PR is present."""
    payload = {"repository": {"full_name": "org/repo"}, "issue": {"number": 3}}
    assert parse_webhook_target(payload) == ("org/repo", 3)


def test_parse_webhook_target_empty():
    """Empty payloads yield empty repo and zero number."""
    assert parse_webhook_target({}) == ("", 0)
