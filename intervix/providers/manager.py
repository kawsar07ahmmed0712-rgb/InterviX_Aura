from __future__ import annotations

import asyncio
import logging

from intervix.config import AppSettings
from intervix.models import ModelReply
from intervix.providers.base import ProviderError
from intervix.providers.gemini import GeminiProvider
from intervix.providers.ollama import OllamaProvider

logger = logging.getLogger("intervix_aura.providers")


class ProviderManager:
    def __init__(self, settings: AppSettings, client) -> None:
        self.settings = settings
        self.client = client
        self.providers = {
            "gemini": GeminiProvider(settings, client),
            "ollama": OllamaProvider(settings, client),
        }

    async def health(self) -> dict[str, object]:
        ollama_ready = await self.providers["ollama"].is_available()
        return {
            "ok": bool(self.settings.gemini_api_key) or ollama_ready,
            "defaultProvider": self._normalize_provider(self.settings.model_provider),
            "geminiConfigured": bool(self.settings.gemini_api_key),
            "geminiModel": self.settings.gemini_model,
            "ollamaAvailable": ollama_ready,
            "ollamaModel": self.settings.ollama_model,
        }

    def _normalize_provider(self, provider: str | None) -> str:
        normalized = (provider or "auto").strip().lower()
        return normalized if normalized in {"auto", "gemini", "ollama"} else "auto"

    async def resolve_provider_chain(self, requested_provider: str | None) -> list[str]:
        provider = self._normalize_provider(requested_provider or self.settings.model_provider)
        ollama_ready = await self.providers["ollama"].is_available()

        if provider == "ollama":
            return ["ollama"]

        if provider == "gemini":
            chain = ["gemini"]
            if ollama_ready:
                chain.append("ollama")
            return chain

        chain: list[str] = []
        if self.settings.gemini_api_key:
            chain.append("gemini")
        if ollama_ready:
            chain.append("ollama")
        if not chain:
            chain.append("ollama")
        return chain

    async def _call_provider(
        self,
        provider_name: str,
        messages: list[dict[str, str]],
        expect_json: bool = False,
    ) -> str:
        provider = self.providers[provider_name]
        last_error: ProviderError | None = None

        for attempt in range(1, self.settings.provider_max_retries + 1):
            try:
                return await provider.generate(messages, expect_json=expect_json)
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.settings.provider_max_retries:
                    raise
                await asyncio.sleep(self.settings.provider_retry_base_seconds * (2 ** (attempt - 1)))

        raise last_error or ProviderError(provider=provider_name, message="Unknown provider error.")

    def _humanize_provider_error(self, provider: str, error: ProviderError) -> str:
        lowered = str(error).lower()
        if provider == "gemini":
            if "quota" in lowered or error.status_code == 429:
                return "Gemini quota is currently exhausted."
            if "api key" in lowered or error.status_code in {401, 403}:
                return "Gemini API access failed. Check GEMINI_API_KEY and project access."
            return f"Gemini error: {str(error)[:180]}"

        if "refused" in lowered or "connect" in lowered or "failed" in lowered:
            return f"Ollama is not reachable at {self.settings.ollama_base_url}."
        if "not found" in lowered:
            return f"Ollama model '{self.settings.ollama_model}' is not installed."
        return f"Ollama error: {str(error)[:180]}"

    async def generate(
        self,
        messages: list[dict[str, str]],
        requested_provider: str | None,
        expect_json: bool = False,
        session_id: str = "",
        correlation_id: str = "",
    ) -> ModelReply:
        provider_chain = await self.resolve_provider_chain(requested_provider)
        errors: list[str] = []

        for index, provider_name in enumerate(provider_chain):
            try:
                text = await self._call_provider(
                    provider_name=provider_name,
                    messages=messages,
                    expect_json=expect_json,
                )
                notice = None
                if index > 0 and errors:
                    notice = f"Switched to {provider_name.title()} because {errors[-1].rstrip('.')}"
                return ModelReply(
                    provider=provider_name,
                    model_name=self.providers[provider_name].model_name,
                    text=text,
                    notice=notice,
                )
            except ProviderError as exc:
                humanized = self._humanize_provider_error(provider_name, exc)
                logger.warning(
                    "provider_failure provider=%s session_id=%s correlation_id=%s reason=%s",
                    provider_name,
                    session_id,
                    correlation_id,
                    humanized,
                )
                errors.append(humanized)

        if errors:
            raise RuntimeError(errors[-1])
        raise RuntimeError("No model provider is configured.")
