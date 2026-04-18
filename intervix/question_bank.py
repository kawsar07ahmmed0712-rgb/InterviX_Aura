from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
QUESTION_BANK_PATH = BASE_DIR / "data" / "question_bank.json"


@lru_cache
def load_question_bank() -> dict[str, dict[str, object]]:
    return json.loads(QUESTION_BANK_PATH.read_text(encoding="utf-8"))


def _match_role_family(role: str) -> str:
    bank = load_question_bank()
    lowered = role.lower()
    for family, payload in bank.items():
        keywords = payload.get("keywords", [])
        if family == "default":
            continue
        if any(keyword in lowered for keyword in keywords):
            return family
    return "default"


def get_question_seeds(
    role: str,
    interview_type: str,
    used_questions: list[str],
    limit: int = 4,
) -> list[str]:
    bank = load_question_bank()
    family = _match_role_family(role)
    used = {question.casefold() for question in used_questions}

    candidates: list[str] = []
    for name in (family, "default"):
        payload = bank.get(name, {})
        for key in (interview_type, "mixed"):
            for item in payload.get(key, []):
                question = str(item).strip()
                if question and question.casefold() not in used and question not in candidates:
                    candidates.append(question)
                if len(candidates) >= limit:
                    return candidates
    return candidates[:limit]
