from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ProviderResult:
    provider: str
    model: str
    text: str


class BaseChatProvider:
    def __init__(self, provider_name: str, base_url: str, api_key: str, model: str) -> None:
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str) -> ProviderResult:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseChatProvider):
    async def complete(self, prompt: str) -> ProviderResult:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": "你是投流风控分析助手。请用中文输出简洁、明确、可执行的结论。",
                },
                {"role": "user", "content": prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        return ProviderResult(
            provider=self.provider_name,
            model=self.model,
            text=content or "模型未返回内容。",
        )
