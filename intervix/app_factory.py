from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState

from intervix.config import AppSettings, BASE_DIR, get_settings
from intervix.interview import InterviewService
from intervix.models import CompanyStyle, Difficulty, InterviewType, ProviderChoice, SessionConfig
from intervix.providers import ProviderManager
from intervix.rate_limit import RateLimiter
from intervix.repository import SessionRepository
from intervix.utils import build_transcript_items

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


def create_app(
    settings: AppSettings | None = None,
    provider_manager=None,
    repository: SessionRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        http_client = httpx.AsyncClient(timeout=resolved_settings.provider_timeout_seconds)
        repo = repository or SessionRepository(resolved_settings.db_path)
        repo.initialize()
        manager = provider_manager or ProviderManager(resolved_settings, http_client)

        app.state.settings = resolved_settings
        app.state.http_client = http_client
        app.state.repository = repo
        app.state.provider_manager = manager
        app.state.rate_limiter = RateLimiter()
        yield
        await http_client.aclose()

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def read_root(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"request": request, "max_questions": resolved_settings.max_questions},
        )

    @app.get("/health")
    async def health() -> dict[str, object]:
        return await app.state.provider_manager.health()

    @app.get("/api/sessions")
    async def list_sessions(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, object]:
        items = app.state.repository.list_sessions(limit=limit)
        return {"items": [item.model_dump(mode="json") for item in items]}

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> dict[str, object]:
        snapshot = app.state.repository.get_session(session_id)
        if snapshot is None:
            return {"ok": False, "message": "Session not found."}
        return {
            "ok": True,
            "session": {
                **snapshot.model_dump(mode="json"),
                "transcript": build_transcript_items(snapshot.turns),
            },
        }

    @app.websocket("/ws/interview")
    async def websocket_endpoint(
        websocket: WebSocket,
        role: Annotated[str, Query(min_length=2, max_length=60)] = "AI Engineer",
        provider: ProviderChoice = ProviderChoice.auto,
        question_count: Annotated[int, Query(ge=2, le=8)] = 4,
        difficulty: Difficulty = Difficulty.mid,
        interview_type: InterviewType = InterviewType.mixed,
        company_style: CompanyStyle = CompanyStyle.neutral,
        language: Annotated[str, Query(min_length=2, max_length=24)] = "English",
        session_id: str | None = Query(default=None, min_length=8, max_length=64),
    ) -> None:
        await websocket.accept()
        config = SessionConfig(
            role=role,
            provider=provider,
            question_count=question_count,
            difficulty=difficulty,
            interview_type=interview_type,
            company_style=company_style,
            language=language,
        )
        service = InterviewService(
            settings=app.state.settings,
            provider_manager=app.state.provider_manager,
            repository=app.state.repository,
            rate_limiter=app.state.rate_limiter,
        )
        await service.run(websocket=websocket, config=config, requested_session_id=session_id)
        if websocket.application_state is not WebSocketState.DISCONNECTED:
            await websocket.close()

    return app
