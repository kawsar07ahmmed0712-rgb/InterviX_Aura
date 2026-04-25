import os
from typing import Optional

from dotenv import load_dotenv
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv()


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/")

OLLAMA_MODEL_ALIASES = {
    "deepseek": os.getenv("OLLAMA_DEEPSEEK_MODEL", "deepseek-v3.1:671b-cloud"),
    "deepseek-v3.1": os.getenv("OLLAMA_DEEPSEEK_MODEL", "deepseek-v3.1:671b-cloud"),
    "deepseek-v3.1:671b-cloud": os.getenv("OLLAMA_DEEPSEEK_MODEL", "deepseek-v3.1:671b-cloud"),

    "llama3": os.getenv("OLLAMA_LLAMA_MODEL", "llama3:latest"),
    "llama3:latest": os.getenv("OLLAMA_LLAMA_MODEL", "llama3:latest"),

    "gemma3:1b": os.getenv("OLLAMA_GEMMA_SMALL_MODEL", "gemma3:1b"),
    "gemma3:4b": os.getenv("OLLAMA_GEMMA_MEDIUM_MODEL", "gemma3:4b"),

    "gpt-oss": os.getenv("OLLAMA_GPT_OSS_MODEL", "gpt-oss:120b-cloud"),
    "gpt-oss:120b-cloud": os.getenv("OLLAMA_GPT_OSS_MODEL", "gpt-oss:120b-cloud"),
}


def _model_family(name: str, fallback: str = "unknown") -> str:
    return getattr(ModelFamily, name, fallback)


def _gemini_model_info(model: str) -> dict:
    family_by_model = {
        "gemini-2.5-flash": _model_family("GEMINI_2_5_FLASH", "gemini-2.5-flash"),
        "gemini-2.5-pro": _model_family("GEMINI_2_5_PRO", "gemini-2.5-pro"),
    }

    return {
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": family_by_model.get(model, _model_family("UNKNOWN")),
        "structured_output": True,
    }


def _ollama_model_info(model: str) -> dict:
    model_lower = model.lower()

    if "deepseek-r1" in model_lower or model_lower.endswith("-r1") or ":r1" in model_lower:
        family = _model_family("R1")
    elif "llama" in model_lower:
        family = _model_family("LLAMA")
    else:
        family = _model_family("UNKNOWN")

    return {
        "vision": False,
        "function_calling": False,
        "json_output": False,
        "family": family,
        "structured_output": False,
    }


def resolve_ollama_model(model: Optional[str]) -> str:
    if not model:
        return OLLAMA_MODEL_ALIASES["deepseek"]

    normalized_model = model.strip()
    return OLLAMA_MODEL_ALIASES.get(normalized_model.lower(), normalized_model)


def build_model_client(
    provider: str = "gemini",
    model: Optional[str] = None,
) -> OpenAIChatCompletionClient:
    provider = provider.lower().strip()

    if provider == "gemini":
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing from .env")

        selected_model = model or GEMINI_MODEL

        return OpenAIChatCompletionClient(
            model=selected_model,
            api_key=GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
            model_info=_gemini_model_info(selected_model),
            temperature=0.4,
            include_name_in_message=False,
            add_name_prefixes=True,
        )

    if provider == "ollama":
        selected_model = resolve_ollama_model(model)

        return OpenAIChatCompletionClient(
            model=selected_model,
            api_key="ollama",
            base_url=OLLAMA_BASE_URL,
            model_info=_ollama_model_info(selected_model),
            temperature=0.4,
            include_name_in_message=False,
            add_name_prefixes=True,
        )

    raise ValueError("provider must be either 'gemini' or 'ollama'")
