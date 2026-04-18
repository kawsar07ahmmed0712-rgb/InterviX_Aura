from __future__ import annotations

import httpx

from intervix.providers.base import BaseProvider, ProviderError


class OllamaProvider(BaseProvider):
    name = "ollama"

    @property
    def model_name(self) -> str:
        return self.settings.ollama_model

    async def is_available(self) -> bool:
        try:
            response = await self.client.get(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/tags",
                timeout=self.settings.provider_health_timeout_seconds,
            )
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def generate(self, messages: list[dict[str, str]], expect_json: bool = False) -> str:
        payload: dict[str, object] = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
        }
        if expect_json:
            payload["format"] = "json"

        try:
            response = await self.client.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=self.settings.provider_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                provider=self.name,
                message="Ollama timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                provider=self.name,
                message=f"Ollama request failed: {exc}",
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 429, 500, 502, 503, 504}
            message = response.text.strip() or f"Ollama returned HTTP {response.status_code}."
            raise ProviderError(
                provider=self.name,
                message=message,
                retryable=retryable,
                status_code=response.status_code,
            )

        data = response.json()
        content = str(data.get("message", {}).get("content", "")).strip()
        if not content:
            raise ProviderError(
                provider=self.name,
                message="Ollama returned an empty response.",
                retryable=True,
            )
        return content
