"""Tests for the Qwen LLM client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent import DEFAULT_BASE_URL, DEFAULT_MODEL, QwenClient


def _mock_http_client(mock_client_class: MagicMock, response_json: dict) -> AsyncMock:
    """Wire up a mocked httpx.AsyncClient returning ``response_json``."""
    mock_client = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response
    return mock_client


@pytest.mark.asyncio
async def test_generate_response_success():
    """The client returns the parsed JSON from the API."""
    expected = {"choices": [{"message": {"content": "Hello!"}}]}
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = _mock_http_client(mock_client_class, expected)

        client = QwenClient(api_key="test-key-for-unit-testing")
        result = await client.generate_response("Hi")

        assert result == expected
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_generate_response_sends_system_prompt():
    """A system prompt is prepended to the messages payload."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = _mock_http_client(mock_client_class, {"choices": []})

        client = QwenClient(api_key="test-key")
        await client.generate_response("Hi", system_prompt="Be safe")

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["messages"][0] == {"role": "system", "content": "Be safe"}
        assert payload["messages"][1] == {"role": "user", "content": "Hi"}


def test_missing_api_key_raises(monkeypatch):
    """Constructing without an API key raises ValueError."""
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    with pytest.raises(ValueError):
        QwenClient()


def test_defaults():
    """Base URL and model fall back to the documented defaults."""
    client = QwenClient(api_key="k")
    assert client.base_url == DEFAULT_BASE_URL
    assert client.model == DEFAULT_MODEL


def test_custom_url_and_model():
    """Explicit constructor arguments override the defaults."""
    client = QwenClient(api_key="k", url="https://example.com/v1", model="qwen-plus")
    assert client.base_url == "https://example.com/v1"
    assert client.model == "qwen-plus"


def test_build_messages_without_system():
    """Without a system prompt only the user message is present."""
    client = QwenClient(api_key="k")
    messages = client.build_messages("hello")
    assert messages == [{"role": "user", "content": "hello"}]
