from __future__ import annotations

from dataclasses import dataclass

from intervix.config import AppSettings


@dataclass
class ProviderError(RuntimeError):
    provider: str
    message: str
    retryable: bool = False
    status_code: int | None = None

    def __str__(self) -> str:
        return self.message


class BaseProvider:
    name = "base"

    def __init__(self, settings: AppSettings, client) -> None:
        self.settings = settings
        self.client = client

    @property
    def model_name(self) -> str:
        raise NotImplementedError

    async def is_available(self) -> bool:
        raise NotImplementedError

    async def generate(self, messages: list[dict[str, str]], expect_json: bool = False) -> str:
        raise NotImplementedError
