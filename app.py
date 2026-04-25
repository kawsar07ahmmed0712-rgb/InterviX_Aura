from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from interview_team import (
    close_model_clients,
    create_interview_team,
    format_stream_message,
)


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="AI Interview Practice App")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class WebSocketInputHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def get_input(self, prompt: str, cancellation_token: Optional[object] = None) -> str:
        try:
            await self.websocket.send_text("SYSTEM_TURN:USER")
            answer = await self.websocket.receive_text()
            return answer.strip() or "No answer provided."
        except WebSocketDisconnect:
            return "TERMINATE"


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.websocket("/ws/interview")
async def websocket_endpoint(
    websocket: WebSocket,
    pos: str = Query("AI Engineer"),
    provider: str = Query("gemini"),
    model: Optional[str] = Query(None),
):
    await websocket.accept()

    clients = []

    try:
        input_handler = WebSocketInputHandler(websocket)

        team, clients = create_interview_team(
            job_position=pos,
            input_func=input_handler.get_input,
            provider=provider,
            model=model,
        )

        selected_model = model or "default"
        await websocket.send_text(
            f"SYSTEM_INFO:Starting interview for {pos} using {provider}:{selected_model}"
        )

        async for message in team.run_stream(task="Start the interview with the first question."):
            source, content = format_stream_message(message)
            await websocket.send_text(f"{source}:{content}")

    except WebSocketDisconnect:
        print("WebSocket disconnected.")

    except Exception as error:
        error_message = f"{type(error).__name__}: {error}"
        print(error_message)

        try:
            await websocket.send_text(f"SYSTEM_ERROR:{error_message}")
        except Exception:
            pass

    finally:
        await close_model_clients(clients)
