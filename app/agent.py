"""Qwen LLM client speaking the OpenAI-compatible chat completions protocol."""

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-max"
DEFAULT_TIMEOUT = 120.0


class QwenClient:
    """Thin async client for a Qwen (or any OpenAI-compatible) endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("QWEN_API_KEY")
        self.base_url = (
            url or os.environ.get("QWEN_BASE_URL") or DEFAULT_BASE_URL
        )
        self.model = model or os.environ.get("QWEN_MODEL") or DEFAULT_MODEL
        if not self.api_key:
            raise ValueError("Qwen API key is required.")

    def build_messages(
        self, prompt: str, system_prompt: str | None = None
    ) -> list[dict[str, str]]:
        """Build the chat messages payload for a request."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Send a chat completion request and return the parsed JSON response."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": self.build_messages(prompt, system_prompt),
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
