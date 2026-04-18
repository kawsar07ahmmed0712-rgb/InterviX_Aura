from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from intervix.config import AppSettings
from intervix.models import (
    FeedbackPayload,
    ModelReply,
    SessionConfig,
    SessionSnapshot,
    SessionStatus,
    SessionSummary,
    TurnRecord,
)
from intervix.prompts import render_prompt
from intervix.question_bank import get_question_seeds
from intervix.rate_limit import RateLimiter
from intervix.repository import SessionRepository
from intervix.utils import (
    aggregate_feedback,
    build_progress_labels,
    build_transcript_items,
    clean_question,
    estimate_session_minutes,
    feedback_to_markdown,
    format_history,
    now_iso,
    parse_feedback_payload,
    parse_summary_payload,
    sanitize_answer,
)

logger = logging.getLogger("intervix_aura.interview")


class SocketEventStream:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def emit(self, event_type: str, **payload: Any) -> None:
        await self.websocket.send_json({"type": event_type, **payload})


class WebSocketInputHandler:
    def __init__(
        self,
        websocket: WebSocket,
        events: SocketEventStream,
        settings: AppSettings,
        rate_limiter: RateLimiter,
    ) -> None:
        self.websocket = websocket
        self.events = events
        self.settings = settings
        self.rate_limiter = rate_limiter

    async def get_input(self, prompt: str, session_id: str) -> str | None:
        await self.events.emit(
            "input_request",
            enabled=True,
            prompt=prompt,
            maxChars=self.settings.answer_max_chars,
        )
        await self.events.emit(
            "status",
            state="awaiting_candidate",
            label="Your Turn",
            message="Reply as the candidate to continue the interview.",
        )

        while True:
            try:
                message = await self.websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("client_disconnected session_id=%s", session_id)
                return None

            allowed = await self.rate_limiter.allow(
                key=f"messages:{session_id}",
                limit=self.settings.rate_limit_messages,
                window_seconds=self.settings.rate_limit_window_seconds,
            )
            if not allowed:
                await self.events.emit(
                    "note",
                    message="You are sending messages too quickly. Wait a moment and try again.",
                    tone="warning",
                )
                continue

            cleaned = sanitize_answer(message)
            if not cleaned:
                await self.events.emit(
                    "note",
                    message="Please send a real answer before continuing.",
                    tone="warning",
                )
                continue
            if len(cleaned) > self.settings.answer_max_chars:
                await self.events.emit(
                    "validation_error",
                    field="answer",
                    message=f"Keep the answer under {self.settings.answer_max_chars} characters.",
                    maxChars=self.settings.answer_max_chars,
                )
                continue
            await self.events.emit("input_request", enabled=False)
            return cleaned


class InterviewService:
    def __init__(
        self,
        settings: AppSettings,
        provider_manager,
        repository: SessionRepository,
        rate_limiter: RateLimiter,
    ) -> None:
        self.settings = settings
        self.provider_manager = provider_manager
        self.repository = repository
        self.rate_limiter = rate_limiter

    def _new_snapshot(self, config: SessionConfig) -> SessionSnapshot:
        timestamp = now_iso()
        return SessionSnapshot(
            session_id=uuid.uuid4().hex,
            correlation_id=uuid.uuid4().hex[:12],
            config=config,
            progress_labels=build_progress_labels(config),
            estimated_minutes=estimate_session_minutes(config),
            status=SessionStatus.starting,
            created_at=timestamp,
            updated_at=timestamp,
        )

    async def _emit_provider_notice(
        self,
        events: SocketEventStream,
        session: SessionSnapshot,
        reply: ModelReply,
    ) -> None:
        provider_changed = (
            reply.provider != session.active_provider or reply.model_name != session.active_model
        )
        if provider_changed:
            session.active_provider = reply.provider
            session.active_model = reply.model_name
            self.repository.update_session(
                session.session_id,
                active_provider=session.active_provider,
                active_model=session.active_model,
            )
            await events.emit(
                "provider_update",
                provider=reply.provider,
                model=reply.model_name,
                reason=reply.notice or f"Active provider changed to {reply.provider}.",
            )
        elif reply.notice:
            await events.emit("note", message=reply.notice, tone="info")

    def _serialize_session(self, session: SessionSnapshot) -> dict[str, Any]:
        return {
            "sessionId": session.session_id,
            "correlationId": session.correlation_id,
            "role": session.config.role,
            "provider": session.active_provider or session.config.provider,
            "model": session.active_model,
            "requestedProvider": session.config.provider,
            "totalQuestions": session.config.question_count,
            "progressLabels": session.progress_labels,
            "estimatedMinutes": session.estimated_minutes,
            "difficulty": session.config.difficulty,
            "interviewType": session.config.interview_type,
            "companyStyle": session.config.company_style,
            "language": session.config.language,
            "status": session.status,
        }

    def _build_feedback_context(self, feedback: FeedbackPayload) -> dict[str, Any]:
        aggregate = aggregate_feedback([])  # keeps the keys consistent
        aggregate["strengths"] = feedback.strengths[:2]
        aggregate["weak_areas"] = feedback.weak_areas[:2]
        aggregate["average_score"] = feedback.scores.average
        return aggregate

    async def _generate_question(
        self,
        session: SessionSnapshot,
        question_index: int,
    ) -> ModelReply:
        prior_feedback = session.turns[-1].feedback if session.turns else None
        focus_label = session.progress_labels[question_index - 1]
        question_seeds = get_question_seeds(
            role=session.config.role,
            interview_type=str(session.config.interview_type),
            used_questions=[turn.question for turn in session.turns],
        )
        probe_mode = bool(prior_feedback and prior_feedback.weak_answer)

        messages = [
            {
                "role": "system",
                "content": render_prompt("question_system.txt"),
            },
            {
                "role": "user",
                "content": render_prompt(
                    "question_user.txt",
                    role=session.config.role,
                    difficulty=session.config.difficulty,
                    interview_type=session.config.interview_type,
                    company_style=session.config.company_style,
                    language=session.config.language,
                    question_number=question_index,
                    total_questions=session.config.question_count,
                    focus_label=focus_label,
                    mode="Probe the previous weak answer." if probe_mode else "Ask the next best question.",
                    transcript=format_history(session.turns),
                    previous_feedback=feedback_to_markdown(prior_feedback) if prior_feedback else "No previous feedback.",
                    question_seeds="\n".join(f"- {seed}" for seed in question_seeds) or "- No bank seed available.",
                    repeated_weaknesses=", ".join(aggregate_feedback(session.turns)["weak_areas"]) or "None yet.",
                ),
            },
        ]
        reply = await self.provider_manager.generate(
            messages=messages,
            requested_provider=str(session.config.provider),
            expect_json=False,
            session_id=session.session_id,
            correlation_id=session.correlation_id,
        )
        cleaned = clean_question(reply.text)
        if not cleaned and question_seeds:
            cleaned = question_seeds[0]
        reply.text = cleaned or "Walk me through a strong example from your recent work."
        return reply

    async def _generate_feedback(
        self,
        session: SessionSnapshot,
        question: str,
        answer: str,
    ) -> tuple[ModelReply, FeedbackPayload]:
        messages = [
            {"role": "system", "content": render_prompt("feedback_system.txt")},
            {
                "role": "user",
                "content": render_prompt(
                    "feedback_user.txt",
                    role=session.config.role,
                    difficulty=session.config.difficulty,
                    interview_type=session.config.interview_type,
                    company_style=session.config.company_style,
                    language=session.config.language,
                    question=question,
                    answer=answer,
                    transcript=format_history(session.turns),
                ),
            },
        ]
        reply = await self.provider_manager.generate(
            messages=messages,
            requested_provider=str(session.config.provider),
            expect_json=True,
            session_id=session.session_id,
            correlation_id=session.correlation_id,
        )
        feedback = parse_feedback_payload(reply.text, answer, str(session.config.interview_type))
        return reply, feedback

    async def _generate_summary(self, session: SessionSnapshot) -> tuple[ModelReply, SessionSummary]:
        aggregates = aggregate_feedback(session.turns)
        messages = [
            {"role": "system", "content": render_prompt("summary_system.txt")},
            {
                "role": "user",
                "content": render_prompt(
                    "summary_user.txt",
                    role=session.config.role,
                    difficulty=session.config.difficulty,
                    interview_type=session.config.interview_type,
                    company_style=session.config.company_style,
                    language=session.config.language,
                    transcript=format_history(session.turns),
                    average_score=round(aggregates["average_score"], 2),
                    top_strengths=", ".join(aggregates["strengths"]) or "None",
                    top_weak_areas=", ".join(aggregates["weak_areas"]) or "None",
                ),
            },
        ]
        reply = await self.provider_manager.generate(
            messages=messages,
            requested_provider=str(session.config.provider),
            expect_json=True,
            session_id=session.session_id,
            correlation_id=session.correlation_id,
        )
        summary = parse_summary_payload(reply.text, session.turns)
        return reply, summary

    async def _ensure_current_question(
        self,
        session: SessionSnapshot,
        events: SocketEventStream,
    ) -> None:
        if session.current_question:
            return
        session.current_question_index = max(1, len(session.turns) + 1)
        reply = await self._generate_question(session, session.current_question_index)
        await self._emit_provider_notice(events, session, reply)
        session.current_question = reply.text
        session.waiting_for_answer = True
        session.status = SessionStatus.awaiting_answer
        self.repository.update_session(
            session.session_id,
            active_provider=session.active_provider,
            active_model=session.active_model,
            status=session.status,
            current_question_index=session.current_question_index,
            current_question=session.current_question,
            waiting_for_answer=True,
        )

    async def run(
        self,
        websocket: WebSocket,
        config: SessionConfig,
        requested_session_id: str | None = None,
    ) -> None:
        events = SocketEventStream(websocket)
        client_host = websocket.client.host if websocket.client else "unknown"
        allowed = await self.rate_limiter.allow(
            key=f"connect:{client_host}",
            limit=self.settings.rate_limit_connections,
            window_seconds=self.settings.rate_limit_window_seconds,
        )
        if not allowed:
            await events.emit("error", message="Rate limit hit. Wait a minute before starting another session.")
            return

        session = self.repository.get_session(requested_session_id) if requested_session_id else None
        is_resume = bool(session and session.status != SessionStatus.completed)
        if session is None or session.status == SessionStatus.completed:
            session = self._new_snapshot(config)
            self.repository.create_session(session)
        else:
            session.correlation_id = uuid.uuid4().hex[:12]
            session.status = SessionStatus.awaiting_answer if session.waiting_for_answer else SessionStatus.starting
            self.repository.update_session(
                session.session_id,
                correlation_id=session.correlation_id,
                status=session.status,
            )

        handler = WebSocketInputHandler(
            websocket=websocket,
            events=events,
            settings=self.settings,
            rate_limiter=self.rate_limiter,
        )

        try:
            await events.emit(
                "status",
                state="starting",
                label="Starting",
                message=f"Preparing an interview for {session.config.role}.",
            )
            await self._ensure_current_question(session, events)
            await events.emit("session", **self._serialize_session(session))
            if session.turns:
                await events.emit("history_sync", transcript=build_transcript_items(session.turns))
            if is_resume:
                await events.emit(
                    "note",
                    message="Resumed your unfinished session from the last saved step.",
                    tone="info",
                )

            while True:
                label = session.progress_labels[session.current_question_index - 1]
                await events.emit(
                    "progress",
                    current=session.current_question_index,
                    total=session.config.question_count,
                    labels=session.progress_labels,
                    currentLabel=label,
                )
                await events.emit(
                    "message",
                    actor="Interviewer",
                    role="interviewer",
                    content=session.current_question,
                    meta=f"Question {session.current_question_index} of {session.config.question_count} • {label}",
                )

                answer = await handler.get_input(
                    prompt="Share your answer and press Enter to send.",
                    session_id=session.session_id,
                )
                if answer is None:
                    session.status = SessionStatus.interrupted
                    self.repository.mark_interrupted(session.session_id)
                    return

                session.status = SessionStatus.evaluating
                self.repository.update_session(
                    session.session_id,
                    status=session.status,
                    waiting_for_answer=False,
                )
                await events.emit(
                    "status",
                    state="evaluating",
                    label="Coach",
                    message="Scoring your answer and preparing feedback.",
                )

                feedback_reply, feedback = await self._generate_feedback(
                    session=session,
                    question=session.current_question,
                    answer=answer,
                )
                await self._emit_provider_notice(events, session, feedback_reply)

                turn = TurnRecord(
                    turn_index=session.current_question_index,
                    focus_label=label,
                    question=session.current_question,
                    answer=answer,
                    feedback=feedback,
                    provider=session.active_provider,
                    model=session.active_model,
                    created_at=now_iso(),
                )
                session.turns.append(turn)
                self.repository.add_turn(session.session_id, turn)

                aggregates = aggregate_feedback(session.turns)
                await events.emit(
                    "feedback",
                    count=len(session.turns),
                    scores={
                        "clarity": feedback.scores.clarity,
                        "relevance": feedback.scores.relevance,
                        "technical_depth": feedback.scores.technical_depth,
                        "confidence": feedback.scores.confidence,
                        "average": feedback.scores.average,
                    },
                )
                await events.emit(
                    "mini_summary",
                    strengths=aggregates["strengths"],
                    weakAreas=aggregates["weak_areas"],
                    averageScore=aggregates["average_score"],
                )
                await events.emit(
                    "message",
                    actor="Coach",
                    role="evaluator",
                    content=feedback_to_markdown(feedback),
                    meta=f"Coach feedback • Avg {feedback.scores.average}/10",
                )

                if session.current_question_index >= session.config.question_count:
                    summary_reply, summary = await self._generate_summary(session)
                    await self._emit_provider_notice(events, session, summary_reply)
                    session.summary = summary
                    session.status = SessionStatus.completed
                    session.waiting_for_answer = False
                    session.current_question = None
                    self.repository.complete_session(session.session_id, summary)
                    await events.emit("summary", summary=summary.model_dump(mode="json"))
                    await events.emit(
                        "complete",
                        reason="interview_complete",
                        sessionId=session.session_id,
                        totalQuestions=session.config.question_count,
                        finalScore=summary.final_score,
                    )
                    return

                next_index = session.current_question_index + 1
                next_reply = await self._generate_question(session, next_index)
                await self._emit_provider_notice(events, session, next_reply)
                session.current_question_index = next_index
                session.current_question = next_reply.text
                session.waiting_for_answer = True
                session.status = SessionStatus.awaiting_answer
                self.repository.update_session(
                    session.session_id,
                    active_provider=session.active_provider,
                    active_model=session.active_model,
                    status=session.status,
                    current_question_index=session.current_question_index,
                    current_question=session.current_question,
                    waiting_for_answer=True,
                )
                await events.emit(
                    "status",
                    state="ready",
                    label="Live",
                    message="The next interview question is ready.",
                )
        except WebSocketDisconnect:
            session.status = SessionStatus.interrupted
            self.repository.mark_interrupted(session.session_id)
            logger.info("websocket_disconnected session_id=%s", session.session_id)
        except Exception:
            session.status = SessionStatus.error
            self.repository.update_session(session.session_id, status=session.status)
            logger.exception("interview_failed session_id=%s", session.session_id)
            await events.emit(
                "error",
                message="The interview session failed unexpectedly. Retry the same role or switch providers.",
            )
