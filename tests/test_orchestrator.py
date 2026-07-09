"""Tests for the remediation orchestrator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.orchestrator import RemediationOrchestrator, extract_code

SAFE_PATCH = (
    "Here is the fix:\n```python\ndef add(a, b):\n    return a + b\n```"
)
UNSAFE_PATCH = "Fix:\n```python\neval(user_input)\n```"


def _make_agent(contents: list[str]) -> AsyncMock:
    """Build an agent mock returning the given contents in sequence."""
    agent = AsyncMock()
    agent.generate_response.side_effect = [
        {
            "choices": [{"message": {"content": content}}],
            "usage": {"total_tokens": 10},
        }
        for content in contents
    ]
    return agent


def _make_validator(status: int = 0) -> MagicMock:
    validator = MagicMock()
    validator.run_validation.return_value = {
        "pylint_log": "",
        "snyk_log": "",
        "passed": status == 0,
        "status": status,
    }
    return validator


def test_extract_code_from_python_block():
    """Fenced python blocks are extracted."""
    text = "before\n```python\nx = 1\n```\nafter"
    assert extract_code(text) == "x = 1"


def test_extract_code_plain_text():
    """Text without code fences is returned stripped."""
    assert extract_code("  x = 1  ") == "x = 1"


def test_extract_code_picks_largest_block():
    """The largest of multiple code blocks is chosen."""
    text = "```python\na = 1\n```\n```python\nb = 1\nc = 2\n```"
    assert extract_code(text) == "b = 1\nc = 2"


@pytest.mark.asyncio
async def test_remediate_success_first_attempt():
    """A valid patch on attempt one returns the patch with metrics."""
    agent = _make_agent([SAFE_PATCH])
    orchestrator = RemediationOrchestrator(agent, _make_validator(status=0))

    result = await orchestrator.remediate("code", "report")

    assert "Here is the fix" in result
    assert "Total Iterations: 1" in result
    assert "Total Tokens Used: 10" in result
    agent.generate_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_remediate_fails_after_max_retries():
    """Persistent validation failures return the failure message."""
    agent = _make_agent([SAFE_PATCH, SAFE_PATCH, SAFE_PATCH])
    orchestrator = RemediationOrchestrator(agent, _make_validator(status=1))

    result = await orchestrator.remediate("code", "report")

    assert result == "Remediation failed after max retries."
    assert agent.generate_response.await_count == 3


@pytest.mark.asyncio
async def test_remediate_rejects_unsafe_patch_via_scanner():
    """The static scanner blocks patches that reintroduce vulnerabilities."""
    agent = _make_agent([UNSAFE_PATCH, UNSAFE_PATCH, UNSAFE_PATCH])
    orchestrator = RemediationOrchestrator(agent, _make_validator(status=0))

    result = await orchestrator.remediate("code", "report")

    assert result == "Remediation failed after max retries."


@pytest.mark.asyncio
async def test_remediate_retries_then_succeeds():
    """A failing first attempt is retried and the second attempt succeeds."""
    agent = _make_agent([UNSAFE_PATCH, SAFE_PATCH])
    orchestrator = RemediationOrchestrator(agent, _make_validator(status=0))

    result = await orchestrator.remediate("code", "report")

    assert "Total Iterations: 2" in result
    assert agent.generate_response.await_count == 2


@pytest.mark.asyncio
async def test_remediate_feedback_included_in_retry_prompt():
    """Validation feedback is appended to the follow-up prompt."""
    agent = _make_agent([UNSAFE_PATCH, SAFE_PATCH])
    orchestrator = RemediationOrchestrator(agent, _make_validator(status=0))

    await orchestrator.remediate("code", "report")

    second_prompt = agent.generate_response.await_args_list[1].args[0]
    assert "Validation failed (Attempt 1)" in second_prompt
