from __future__ import annotations

import httpx

from intervix.providers.base import BaseProvider, ProviderError


class GeminiProvider(BaseProvider):
    name = "gemini"

    @property
    def model_name(self) -> str:
        return self.settings.gemini_model

    async def is_available(self) -> bool:
        return bool(self.settings.gemini_api_key)

    async def generate(self, messages: list[dict[str, str]], expect_json: bool = False) -> str:
        if not self.settings.gemini_api_key:
            raise ProviderError(
                provider=self.name,
                message="Gemini API key is not configured.",
                retryable=False,
            )

        system_instruction = "\n\n".join(
            message["content"] for message in messages if message["role"] == "system"
        ).strip()
        contents = []
        for message in messages:
            if message["role"] == "system":
                continue
            role = "model" if message["role"] == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": message["content"]}],
                }
            )

        if not contents:
            raise ProviderError(provider=self.name, message="Gemini prompt is empty.", retryable=False)

        payload: dict[str, object] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if expect_json:
            payload["generationConfig"] = {"responseMimeType": "application/json"}

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )

        try:
            response = await self.client.post(
                url,
                params={"key": self.settings.gemini_api_key},
                json=payload,
                timeout=self.settings.provider_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                provider=self.name,
                message="Gemini timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                provider=self.name,
                message=f"Gemini request failed: {exc}",
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            retryable = response.status_code in {408, 409, 429, 500, 502, 503, 504}
            message = response.text.strip() or f"Gemini returned HTTP {response.status_code}."
            raise ProviderError(
                provider=self.name,
                message=message,
                retryable=retryable,
                status_code=response.status_code,
            )

        data = response.json()
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        text = " ".join(part.get("text", "").strip() for part in parts if part.get("text"))
        if not text:
            raise ProviderError(
                provider=self.name,
                message="Gemini returned an empty response.",
                retryable=True,
            )
        return text.strip()
