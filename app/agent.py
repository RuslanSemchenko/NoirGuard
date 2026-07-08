import os
from typing import Any
import httpx

class QwenClient:
    def __init__(self, api_key: str | None = None,
                 url: str | None = None):
        self.api_key = api_key or os.environ.get("QWEN_API_KEY")
        self.base_url = (url or os.environ.get("QWEN_BASE_URL")
                         or "https://dashscope.aliyuncs.com/compatible-mode/v1")
        if not self.api_key:
            raise ValueError("Qwen API key is required.")

    async def generate_response(self, prompt: str,
                                system_prompt: str | None = None,
                                timeout: float = 120.0) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": "qwen-max",
                "messages": messages
            }
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
