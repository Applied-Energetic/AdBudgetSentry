from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from providers import OpenAICompatibleProvider


class ProvidersTests(unittest.TestCase):
    def test_openai_compatible_provider_disables_env_proxy(self) -> None:
        captured: dict[str, object] = {}

        class FakeResponse:
            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict:
                return {"choices": [{"message": {"content": "ok"}}]}

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                captured.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                return False

            async def post(self, *args, **kwargs):
                return FakeResponse()

        provider = OpenAICompatibleProvider(
            provider_name="deepseek",
            base_url="https://api.deepseek.com",
            api_key="token",
            model="deepseek-chat",
        )

        with patch("providers.httpx.AsyncClient", FakeClient):
            result = asyncio.run(provider.complete("test prompt"))

        self.assertEqual(result.text, "ok")
        self.assertEqual(captured.get("trust_env"), False)


if __name__ == "__main__":
    unittest.main()
