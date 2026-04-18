import json

from fastapi.testclient import TestClient

from intervix import create_app
from intervix.config import AppSettings
from intervix.models import ModelReply


class FakeProviderManager:
    def __init__(self) -> None:
        self.question_index = 0

    async def health(self) -> dict[str, object]:
        return {
            "ok": True,
            "defaultProvider": "gemini",
            "geminiConfigured": True,
            "geminiModel": "fake-gemini",
            "ollamaAvailable": True,
            "ollamaModel": "fake-ollama",
        }

    async def generate(
        self,
        messages,
        requested_provider,
        expect_json=False,
        session_id="",
        correlation_id="",
    ) -> ModelReply:
        if expect_json:
            prompt = messages[-1]["content"]
            if "Generate the final report now." in prompt:
                return ModelReply(
                    provider="gemini",
                    model_name="fake-gemini",
                    text=json.dumps(
                        {
                            "final_score": 84,
                            "strengths": ["Clear examples", "Good structure", "Solid ownership"],
                            "weak_areas": ["More trade-offs", "More metrics", "Stronger closing"],
                            "recommendations": [
                                "Give one metric in each answer.",
                                "Call out trade-offs explicitly.",
                                "Lead with your decision sooner.",
                            ],
                            "top_improvements": [
                                "Add deeper technical depth.",
                                "Quantify impact.",
                                "Finish stronger.",
                            ],
                            "readiness": "Strong practice session.",
                            "closing_message": "Good session. Try harder questions next.",
                        }
                    ),
                )
            return ModelReply(
                provider="gemini",
                model_name="fake-gemini",
                text=json.dumps(
                    {
                        "strengths": ["Direct answer", "Relevant example"],
                        "weak_areas": ["Need one more trade-off"],
                        "coaching": ["Add one metric.", "Explain why that decision was correct."],
                        "ideal_answer": "I would frame the goal, describe the action, mention the trade-off, and finish with the measurable result.",
                        "recommendation": "Keep answers concrete and outcome-driven.",
                        "star_tip": "Use STAR for better structure.",
                        "scores": {
                            "clarity": 8,
                            "relevance": 8,
                            "technical_depth": 7,
                            "confidence": 8,
                        },
                        "weak_answer": False,
                        "follow_up_reason": "",
                        "summary_blurb": "Solid answer with room for more depth.",
                    }
                ),
            )

        self.question_index += 1
        return ModelReply(
            provider="gemini",
            model_name="fake-gemini",
            text=f"How would you handle question {self.question_index} for this role?",
        )


def test_websocket_interview_flow_and_saved_session(tmp_path):
    settings = AppSettings(db_path=tmp_path / "test.db")
    with TestClient(create_app(settings=settings, provider_manager=FakeProviderManager())) as client:
        with client.websocket_connect(
            "/ws/interview?role=Frontend%20Developer&question_count=2&difficulty=mid&interview_type=technical&company_style=neutral&language=English"
        ) as websocket:
            session_id = None
            input_requests = 0
            summary_received = False
            complete_received = False

            while not complete_received:
                payload = websocket.receive_json()
                if payload["type"] == "session":
                    session_id = payload["sessionId"]
                    assert payload["totalQuestions"] == 2
                if payload["type"] == "input_request" and payload.get("enabled"):
                    input_requests += 1
                    websocket.send_text(f"My answer number {input_requests} includes one concrete example and impact.")
                if payload["type"] == "summary":
                    summary_received = True
                    assert payload["summary"]["final_score"] == 84
                if payload["type"] == "complete":
                    complete_received = True

        assert session_id is not None
        assert input_requests == 2
        assert summary_received is True

        sessions_response = client.get("/api/sessions")
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()["items"]
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id

        detail_response = client.get(f"/api/sessions/{session_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["ok"] is True
        assert detail["session"]["summary"]["final_score"] == 84
        assert len(detail["session"]["transcript"]) >= 6
