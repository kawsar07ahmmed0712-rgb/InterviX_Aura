from intervix.models import SessionConfig
from intervix.utils import build_progress_labels, clean_question, parse_feedback_payload


def test_clean_question_strips_labels():
    assert clean_question('Question 2: "How would you debug this issue?"') == "How would you debug this issue?"


def test_parse_feedback_payload_fallback_marks_weak_short_answer():
    feedback = parse_feedback_payload("not json", "I would improve it.", "technical")
    assert feedback.weak_answer is True
    assert feedback.scores.technical_depth <= 6
    assert feedback.weak_areas


def test_build_progress_labels_matches_question_count():
    config = SessionConfig(
        role="Frontend Developer",
        provider="auto",
        question_count=5,
        difficulty="senior",
        interview_type="technical",
        company_style="neutral",
        language="English",
    )
    labels = build_progress_labels(config)
    assert len(labels) == 5
    assert labels[0] == "Depth"
