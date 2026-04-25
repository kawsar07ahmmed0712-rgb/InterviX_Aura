import inspect
import json
from typing import Any, Callable, Optional

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

from llm_clients import build_model_client


def create_interview_team(
    job_position: str,
    input_func: Callable[..., Any],
    provider: str = "gemini",
    model: Optional[str] = None,
):
    interviewer_client = build_model_client(provider=provider, model=model)
    evaluator_client = build_model_client(provider=provider, model=model)

    interviewer = AssistantAgent(
        name="Interviewer",
        model_client=interviewer_client,
        description=f"Professional interviewer for a {job_position} role.",
        system_message=f"""
You are a professional interviewer for a {job_position} position.

Rules:
- Ask exactly 3 questions total.
- Ask one clear question at a time.
- Cover these areas:
  1. Technical skill
  2. Problem solving
  3. Culture fit
- Wait for the candidate's answer before moving to the next question.
- Ignore the Evaluator's feedback when deciding the next question.
- Keep each question under 50 words.
- After the third candidate answer and evaluator feedback, say only: TERMINATE
""".strip(),
    )

    candidate = UserProxyAgent(
        name="Candidate",
        description=f"Candidate interviewing for a {job_position} role.",
        input_func=input_func,
    )

    evaluator = AssistantAgent(
        name="Evaluator",
        model_client=evaluator_client,
        description="Interview feedback coach.",
        system_message=f"""
You are a career coach for {job_position} interviews.

Rules:
- Give brief feedback on the candidate's latest answer.
- Maximum 45 words.
- Mention one strength and one improvement.
- Do not ask interview questions.
- Do not say TERMINATE.
""".strip(),
    )

    termination = TextMentionTermination(text="TERMINATE")

    team = RoundRobinGroupChat(
        participants=[interviewer, candidate, evaluator],
        termination_condition=termination,
        max_turns=12,
    )

    return team, [interviewer_client, evaluator_client]


def format_stream_message(message: Any) -> tuple[str, str]:
    if isinstance(message, TaskResult):
        return "SYSTEM_END", str(message.stop_reason)

    source = getattr(message, "source", "SYSTEM")
    content = getattr(message, "content", "")

    if content is None:
        content = ""
    elif not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, default=str)

    return source, content


async def close_model_clients(clients: list[Any]) -> None:
    for client in clients:
        close_method = getattr(client, "close", None)

        if close_method:
            close_result = close_method()

            if inspect.isawaitable(close_result):
                await close_result
