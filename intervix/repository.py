from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from intervix.models import (
    SessionConfig,
    SessionHistoryItem,
    SessionSnapshot,
    SessionStatus,
    SessionSummary,
    TurnRecord,
)
from intervix.utils import now_iso


class SessionRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    interview_type TEXT NOT NULL,
                    company_style TEXT NOT NULL,
                    language TEXT NOT NULL,
                    question_count INTEGER NOT NULL,
                    requested_provider TEXT NOT NULL,
                    active_provider TEXT NOT NULL DEFAULT '',
                    active_model TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    estimated_minutes INTEGER NOT NULL,
                    progress_labels TEXT NOT NULL,
                    current_question_index INTEGER NOT NULL DEFAULT 0,
                    current_question TEXT,
                    waiting_for_answer INTEGER NOT NULL DEFAULT 0,
                    final_score INTEGER,
                    summary_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    focus_label TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    feedback_json TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, turn_index)
                );
                """
            )

    def create_session(self, snapshot: SessionSnapshot) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, correlation_id, role, difficulty, interview_type, company_style,
                    language, question_count, requested_provider, active_provider, active_model,
                    status, estimated_minutes, progress_labels, current_question_index, current_question,
                    waiting_for_answer, final_score, summary_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.session_id,
                    snapshot.correlation_id,
                    snapshot.config.role,
                    snapshot.config.difficulty,
                    snapshot.config.interview_type,
                    snapshot.config.company_style,
                    snapshot.config.language,
                    snapshot.config.question_count,
                    snapshot.config.provider,
                    snapshot.active_provider,
                    snapshot.active_model,
                    snapshot.status,
                    snapshot.estimated_minutes,
                    json.dumps(snapshot.progress_labels),
                    snapshot.current_question_index,
                    snapshot.current_question,
                    1 if snapshot.waiting_for_answer else 0,
                    snapshot.summary.final_score if snapshot.summary else None,
                    snapshot.summary.model_dump_json() if snapshot.summary else None,
                    snapshot.created_at,
                    snapshot.updated_at,
                ),
            )

    def update_session(
        self,
        session_id: str,
        *,
        correlation_id: str | None = None,
        active_provider: str | None = None,
        active_model: str | None = None,
        status: str | None = None,
        current_question_index: int | None = None,
        current_question: str | None = None,
        waiting_for_answer: bool | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[object] = []
        mapping = {
            "correlation_id": correlation_id,
            "active_provider": active_provider,
            "active_model": active_model,
            "status": status,
            "current_question_index": current_question_index,
            "current_question": current_question,
        }
        for key, value in mapping.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        if waiting_for_answer is not None:
            fields.append("waiting_for_answer = ?")
            values.append(1 if waiting_for_answer else 0)
        fields.append("updated_at = ?")
        values.append(now_iso())
        values.append(session_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(fields)} WHERE session_id = ?",
                values,
            )

    def add_turn(self, session_id: str, turn: TurnRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO turns (
                    session_id, turn_index, focus_label, question, answer, feedback_json, provider, model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn.turn_index,
                    turn.focus_label,
                    turn.question,
                    turn.answer,
                    turn.feedback.model_dump_json(),
                    turn.provider,
                    turn.model,
                    turn.created_at,
                ),
            )
            conn.execute(
                """
                UPDATE sessions
                SET updated_at = ?, status = ?, waiting_for_answer = 0
                WHERE session_id = ?
                """,
                (now_iso(), SessionStatus.evaluating.value, session_id),
            )

    def complete_session(self, session_id: str, summary: SessionSummary) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET final_score = ?, summary_json = ?, status = ?, waiting_for_answer = 0, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    summary.final_score,
                    summary.model_dump_json(),
                    SessionStatus.completed.value,
                    now_iso(),
                    session_id,
                ),
            )

    def mark_interrupted(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET status = ?, updated_at = ?
                WHERE session_id = ? AND status != ?
                """,
                (
                    SessionStatus.interrupted.value,
                    now_iso(),
                    session_id,
                    SessionStatus.completed.value,
                ),
            )

    def list_sessions(self, limit: int = 25) -> list[SessionHistoryItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, role, difficulty, interview_type, company_style, question_count,
                       active_provider, final_score, status, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [SessionHistoryItem.model_validate(dict(row)) for row in rows]

    def get_session(self, session_id: str) -> SessionSnapshot | None:
        with self._connect() as conn:
            session_row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session_row is None:
                return None

            turn_rows = conn.execute(
                """
                SELECT turn_index, focus_label, question, answer, feedback_json, provider, model, created_at
                FROM turns
                WHERE session_id = ?
                ORDER BY turn_index ASC
                """,
                (session_id,),
            ).fetchall()

        turns = [
            TurnRecord(
                turn_index=row["turn_index"],
                focus_label=row["focus_label"],
                question=row["question"],
                answer=row["answer"],
                feedback=json.loads(row["feedback_json"]),
                provider=row["provider"],
                model=row["model"],
                created_at=row["created_at"],
            )
            for row in turn_rows
        ]
        config = SessionConfig(
            role=session_row["role"],
            difficulty=session_row["difficulty"],
            interview_type=session_row["interview_type"],
            company_style=session_row["company_style"],
            language=session_row["language"],
            question_count=session_row["question_count"],
            provider=session_row["requested_provider"],
        )
        summary = (
            SessionSummary.model_validate(json.loads(session_row["summary_json"]))
            if session_row["summary_json"]
            else None
        )
        return SessionSnapshot(
            session_id=session_row["session_id"],
            correlation_id=session_row["correlation_id"],
            config=config,
            progress_labels=json.loads(session_row["progress_labels"]),
            estimated_minutes=session_row["estimated_minutes"],
            active_provider=session_row["active_provider"],
            active_model=session_row["active_model"],
            status=session_row["status"],
            current_question_index=session_row["current_question_index"],
            current_question=session_row["current_question"],
            waiting_for_answer=bool(session_row["waiting_for_answer"]),
            turns=turns,
            summary=summary,
            created_at=session_row["created_at"],
            updated_at=session_row["updated_at"],
        )
