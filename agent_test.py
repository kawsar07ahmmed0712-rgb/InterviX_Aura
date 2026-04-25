import argparse
import asyncio
import os
from typing import Optional

from dotenv import load_dotenv

from interview_team import (
    close_model_clients,
    create_interview_team,
    format_stream_message,
)

load_dotenv()


def terminal_input(prompt: str, cancellation_token: Optional[object] = None) -> str:
    print("\nCandidate, answer below:")
    answer = input("> ").strip()
    return answer or "No answer provided."


async def run_interview(position: str, provider: str, model: Optional[str]):
    team, clients = create_interview_team(
        job_position=position,
        input_func=terminal_input,
        provider=provider,
        model=model,
    )

    try:
        async for message in team.run_stream(task="Start the interview with the first question."):
            source, content = format_stream_message(message)

            print("-" * 70)
            print(f"{source}: {content}")

    finally:
        await close_model_clients(clients)


def parse_args():
    parser = argparse.ArgumentParser(description="Run terminal interview agent test.")

    parser.add_argument(
        "--position",
        default="AI Engineer",
        help="Interview job position.",
    )

    parser.add_argument(
        "--provider",
        default=os.getenv("DEFAULT_PROVIDER", "gemini"),
        choices=["gemini", "ollama"],
        help="LLM provider.",
    )

    parser.add_argument(
        "--model",
        default=None,
        help="Model name. Example: gemini-2.5-flash, deepseek-r1, llama3, gemma3:1b",
    )

    return parser.parse_args()


async def main():
    args = parse_args()

    await run_interview(
        position=args.position,
        provider=args.provider,
        model=args.model,
    )


if __name__ == "__main__":
    asyncio.run(main())