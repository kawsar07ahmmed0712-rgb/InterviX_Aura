from __future__ import annotations

from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"


@lru_cache
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def render_prompt(name: str, **context: object) -> str:
    template = load_prompt(name)
    rendered = template
    for key, value in context.items():
        replacement = str(value if value is not None else "")
        rendered = rendered.replace(f"{{{{{key}}}}}", replacement)
    return rendered
