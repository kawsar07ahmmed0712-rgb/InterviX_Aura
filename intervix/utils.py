from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from intervix.models import FeedbackPayload, ScoreCard, SessionConfig, SessionSummary, TurnRecord


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_question(text: str) -> str:
    cleaned = text.strip().strip('"').strip("'")
    cleaned = re.sub(r"^```(?:json|text)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    cleaned = re.sub(r"^(question\s*\d*\s*[:.-]\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(interviewer\s*[:.-]\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().strip('"').strip("'")
    cleaned = " ".join(cleaned.split())
    return cleaned[:320]


def sanitize_answer(text: str) -> str:
    return " ".join((text or "").split()).strip()


def truncate_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]).rstrip(",.;:") + "..."


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    try:
        loaded = json.loads(stripped)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    candidate = stripped[start : end + 1]
    try:
        loaded = json.loads(candidate)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        return {}


def _clamp_score(value: Any, default: int = 6) -> int:
    try:
        numeric = int(round(float(value)))
    except Exception:
        numeric = default
    return max(1, min(10, numeric))


def build_progress_labels(config: SessionConfig) -> list[str]:
    technical = {
        "beginner": [
            "Foundations",
            "Applied Basics",
            "Debugging",
            "Trade-offs",
            "Delivery",
            "Communication",
            "Growth",
            "Wrap-up",
        ],
        "mid": [
            "Core Depth",
            "Execution",
            "Debugging",
            "Trade-offs",
            "Architecture",
            "Collaboration",
            "Ownership",
            "Growth",
        ],
        "senior": [
            "Depth",
            "Architecture",
            "Trade-offs",
            "Leadership",
            "Risk",
            "Scaling",
            "Influence",
            "Strategy",
        ],
    }
    label_map = {
        "technical": technical,
        "system_design": {
            "beginner": ["Requirements", "Components", "Data Flow", "Trade-offs", "Reliability", "Scale", "Risks", "Wrap-up"],
            "mid": ["Scope", "Architecture", "Interfaces", "Scale", "Reliability", "Trade-offs", "Operations", "Leadership"],
            "senior": ["Product Scope", "Architecture", "Bottlenecks", "Capacity", "Trade-offs", "Failure Modes", "Roadmap", "Leadership"],
        },
        "behavioral": {
            "beginner": ["Context", "Actions", "Learning", "Communication", "Teamwork", "Ownership", "Growth", "Wrap-up"],
            "mid": ["Situation", "Actions", "Conflict", "Ownership", "Impact", "Stakeholders", "Reflection", "Growth"],
            "senior": ["Leadership", "Conflict", "Decision Quality", "Influence", "Hiring", "Prioritization", "Reflection", "Growth"],
        },
        "hr": {
            "beginner": ["Motivation", "Fit", "Strengths", "Weak Spots", "Team Style", "Communication", "Growth", "Wrap-up"],
            "mid": ["Motivation", "Role Fit", "Career Story", "Pressure", "Stakeholders", "Feedback", "Growth", "Wrap-up"],
            "senior": ["Leadership Fit", "Strategy", "Influence", "Pressure", "Communication", "Hiring", "Growth", "Closing"],
        },
        "mixed": technical,
    }

    difficulty = config.difficulty.value if hasattr(config.difficulty, "value") else str(config.difficulty)
    interview_type = (
        config.interview_type.value if hasattr(config.interview_type, "value") else str(config.interview_type)
    )
    source = label_map.get(interview_type, technical).get(difficulty, technical["mid"])
    return source[: config.question_count]


def estimate_session_minutes(config: SessionConfig) -> int:
    pacing = {
        "technical": 4,
        "mixed": 4,
        "behavioral": 4,
        "hr": 3,
        "system_design": 6,
    }
    interview_type = (
        config.interview_type.value if hasattr(config.interview_type, "value") else str(config.interview_type)
    )
    per_question = pacing.get(interview_type, 4)
    return max(6, config.question_count * per_question + 2)


def format_history(turns: list[TurnRecord]) -> str:
    if not turns:
        return "No previous transcript."

    lines: list[str] = []
    for turn in turns:
        lines.append(f"Question {turn.turn_index}: {turn.question}")
        lines.append(f"Candidate answer: {turn.answer}")
        lines.append(
            "Feedback: "
            f"Strengths={'; '.join(turn.feedback.strengths[:2]) or 'n/a'} | "
            f"Weak areas={'; '.join(turn.feedback.weak_areas[:2]) or 'n/a'} | "
            f"Scores={turn.feedback.scores.model_dump()}"
        )
    return "\n".join(lines)


def feedback_to_markdown(feedback: FeedbackPayload) -> str:
    lines = [
        f"**Score**: {round(feedback.scores.average, 1)}/10",
        "",
        "**Rubric**",
        f"- Clarity: {feedback.scores.clarity}/10",
        f"- Relevance: {feedback.scores.relevance}/10",
        f"- Technical depth: {feedback.scores.technical_depth}/10",
        f"- Confidence: {feedback.scores.confidence}/10",
        "",
        "**Strengths**",
    ]
    lines.extend(f"- {item}" for item in (feedback.strengths or ["You stayed engaged and answered directly."]))
    lines.extend(["", "**Weak Areas**"])
    lines.extend(f"- {item}" for item in (feedback.weak_areas or ["Add more specificity and evidence."]))
    lines.extend(["", "**Coach Notes**"])
    lines.extend(f"- {item}" for item in (feedback.coaching or ["Tighten structure and add one concrete example."]))
    lines.extend(["", "**Good Answer Example**", feedback.ideal_answer or "Give a more concrete answer with trade-offs and measurable impact."])
    if feedback.recommendation:
        lines.extend(["", f"**Recommendation**: {feedback.recommendation}"])
    if feedback.star_tip:
        lines.extend(["", f"**STAR Tip**: {feedback.star_tip}"])
    return "\n".join(lines).strip()


def aggregate_feedback(turns: list[TurnRecord]) -> dict[str, Any]:
    strength_counter: Counter[str] = Counter()
    weakness_counter: Counter[str] = Counter()
    total = 0.0
    for turn in turns:
        total += turn.feedback.scores.average
        strength_counter.update(item.strip() for item in turn.feedback.strengths if item.strip())
        weakness_counter.update(item.strip() for item in turn.feedback.weak_areas if item.strip())

    average = round(total / len(turns), 2) if turns else 0.0
    return {
        "strengths": [item for item, _ in strength_counter.most_common(3)],
        "weak_areas": [item for item, _ in weakness_counter.most_common(3)],
        "average_score": average,
    }


def build_transcript_items(turns: list[TurnRecord]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for turn in turns:
        items.append(
            {
                "actor": "Interviewer",
                "role": "interviewer",
                "content": turn.question,
                "meta": f"Question {turn.turn_index}",
            }
        )
        items.append(
            {
                "actor": "Candidate",
                "role": "user",
                "content": turn.answer,
                "meta": "Your answer",
            }
        )
        items.append(
            {
                "actor": "Coach",
                "role": "evaluator",
                "content": feedback_to_markdown(turn.feedback),
                "meta": "Coach feedback",
            }
        )
    return items


def parse_feedback_payload(text: str, answer: str, interview_type: str) -> FeedbackPayload:
    data = extract_json_object(text)
    if not data:
        word_count = len(answer.split())
        clarity = 4 if word_count < 20 else 7 if word_count < 100 else 8
        relevance = 5 if word_count < 18 else 7
        technical_depth = 4 if interview_type == "technical" and word_count < 24 else 6
        confidence = 5 if "maybe" in answer.lower() or "not sure" in answer.lower() else 7
        weak_answer = word_count < 18
        return FeedbackPayload(
            strengths=["You answered directly and stayed on topic."],
            weak_areas=[
                "Add one concrete example or measurable outcome.",
                "Explain the trade-off behind your decision more clearly.",
            ],
            coaching=[
                "Use a tighter structure: situation, action, result, learning.",
                "State the impact before the details.",
            ],
            ideal_answer=(
                "Start with the goal, explain your decision, mention one trade-off, "
                "and finish with the measurable result."
            ),
            recommendation="Practice answers that include evidence, scope, and outcome.",
            star_tip="Use STAR: situation, task, action, result." if interview_type in {"behavioral", "hr"} else None,
            scores=ScoreCard(
                clarity=_clamp_score(clarity),
                relevance=_clamp_score(relevance),
                technical_depth=_clamp_score(technical_depth),
                confidence=_clamp_score(confidence),
            ),
            weak_answer=weak_answer,
            follow_up_reason="The answer needs more evidence and sharper trade-offs." if weak_answer else None,
            summary_blurb="Solid start, but the answer needs more depth.",
        )

    scores = data.get("scores", {})
    return FeedbackPayload(
        strengths=data.get("strengths", []),
        weak_areas=data.get("weak_areas", []),
        coaching=data.get("coaching", []),
        ideal_answer=str(data.get("ideal_answer") or "").strip()
        or "Add a sharper structure, better evidence, and a clearer result.",
        recommendation=str(data.get("recommendation") or "").strip()
        or "Keep answers concrete and outcome-driven.",
        star_tip=str(data.get("star_tip")).strip() if data.get("star_tip") else None,
        scores=ScoreCard(
            clarity=_clamp_score(scores.get("clarity")),
            relevance=_clamp_score(scores.get("relevance")),
            technical_depth=_clamp_score(scores.get("technical_depth")),
            confidence=_clamp_score(scores.get("confidence")),
        ),
        weak_answer=bool(data.get("weak_answer")),
        follow_up_reason=str(data.get("follow_up_reason")).strip() if data.get("follow_up_reason") else None,
        summary_blurb=str(data.get("summary_blurb")).strip() if data.get("summary_blurb") else None,
    )


def parse_summary_payload(text: str, turns: list[TurnRecord]) -> SessionSummary:
    aggregates = aggregate_feedback(turns)
    average_score = aggregates["average_score"]
    computed_score = int(round(average_score * 10))
    data = extract_json_object(text)

    if not data:
        return SessionSummary(
            final_score=computed_score,
            strengths=aggregates["strengths"] or ["You stayed engaged and answered directly."],
            weak_areas=aggregates["weak_areas"] or ["Add more evidence and sharper structure."],
            recommendations=[
                "Practice shorter, more structured answers.",
                "Use one measurable outcome in each answer.",
                "Add trade-offs instead of only describing actions.",
            ],
            top_improvements=aggregates["weak_areas"][:3]
            or [
                "Increase answer specificity.",
                "Explain decision trade-offs.",
                "Show stronger ownership language.",
            ],
            readiness=(
                "Strong practice session."
                if computed_score >= 80
                else "Promising, but still uneven."
                if computed_score >= 65
                else "Needs another full practice round."
            ),
            closing_message=(
                "Practice communication more and retry this role with a harder difficulty."
                if computed_score < 75
                else "Good session. Try harder questions next and keep sharpening depth."
            ),
        )

    final_score = data.get("final_score")
    return SessionSummary(
        final_score=max(0, min(100, int(final_score))) if isinstance(final_score, int) else computed_score,
        strengths=data.get("strengths", []) or aggregates["strengths"],
        weak_areas=data.get("weak_areas", []) or aggregates["weak_areas"],
        recommendations=data.get("recommendations", [])
        or [
            "Keep answers crisp, specific, and outcome-driven.",
            "Practice deeper trade-off reasoning.",
            "Use a clearer structure under pressure.",
        ],
        top_improvements=data.get("top_improvements", []) or aggregates["weak_areas"][:3],
        readiness=str(data.get("readiness") or "").strip() or "Keep practicing.",
        closing_message=str(data.get("closing_message") or "").strip()
        or "Review the report, then retry the same role or raise the difficulty.",
    )
