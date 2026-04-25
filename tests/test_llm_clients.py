import asyncio

import pytest

import llm_clients
from llm_clients import build_model_client, resolve_ollama_model


def _close_client(client):
    close_result = client.close()

    if asyncio.iscoroutine(close_result):
        asyncio.run(close_result)


def test_supported_ollama_models_build_without_model_family_errors():
    for model in [
        "deepseek",
        "llama3:latest",
        "gemma3:1b",
        "gpt-oss",
    ]:
        client = build_model_client(provider="ollama", model=model)
        _close_client(client)


def test_ollama_alias_resolution_is_case_insensitive():
    assert resolve_ollama_model("LLAMA3") == resolve_ollama_model("llama3")


def test_gemini_requires_api_key(monkeypatch):
    monkeypatch.setattr(llm_clients, "GEMINI_API_KEY", None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        build_model_client(provider="gemini")


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="provider"):
        build_model_client(provider="unknown")
