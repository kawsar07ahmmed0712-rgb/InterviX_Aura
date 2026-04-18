from dotenv import load_dotenv
import os
from autogen_agentchat.agents import AssistantAgent,UserProxyAgent 
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
load_dotenv()

# Gemini client
gemini_client = OpenAIChatCompletionClient(
    model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_info={
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": True,
    },
)

# Ollama client 1
ollama_client = OllamaChatCompletionClient(
    model="gemma3:1b",
    model_info={
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": True,
    },
)

# Ollama client 2
ollama_qwen_client = OllamaChatCompletionClient(
    model="gemma3:4b",
    model_info={
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": True,
    },
)
user_input = input("your client name:")
if user_input in ["ollama1", "o1", "ollama_client"]:
    model_client = ollama_client
elif user_input in ["ollama2", "o2", "ollama_qwen_client"]:
    model_client = ollama_qwen_client
else:
    model_client = gemini_client
async def my_agents(job_position = "Ai Engeneer"):
    interviewer = AssistantAgent(
        name="Interviewer",
        model_client=model_client,
        description=f"An AI agent that conducts interviews for a {job_position} position",
        system_message=f'''
        You are a professional interviewer conducting an interview for the {job_position} role.

        Your goal is to ask exactly 3 interview questions, one at a time.

        Instructions:
        - Ask only one question per message.
        - Wait for the candidate’s response before asking the next question.
        - Base each next question on the candidate’s previous answer, while also using your expertise in interviewing for this role.
        - Focus the 3 questions on:
        1. technical skills and relevant experience,
        2. problem-solving and decision-making,
        3. cultural fit and collaboration.
        - Ignore any career coaching, feedback, or side conversation. Stay fully in interviewer mode.
        - Keep each question clear, specific, and under 50 words.
        - Do not provide explanations, evaluations, or sample answers during the interview.
        - After the third question, output exactly: TERMINATE
    '''
    )
    
    candidate = UserProxyAgent(
        name= "Candidate",
        description=f"An agent that simulates a candidate for a {job_position} position.",
        input_func=input
    )

    evaluation = AssistantAgent(
        name = "Evaluator",
        model_client= model_client,
        description=f"An AI agent that provides feedback and advice to candidates for a {job_position} position.",
        system_message=f'''
        You are a career coach specializing in preparing candidates for {job_position} interviews.
        Provide constructive feedback on the candidate's responses and suggest improvements.
        After the interview, summarize the candidate's performance and provide actionable advice.
        Make it under 100 words.
    '''
    )
    
    terminate_condition = TextMentionTermination(text="TERMINATE")

    team = RoundRobinGroupChat(
        participants=[interviewer, candidate, evaluation],
        termination_condition= terminate_condition,
        max_turns=20
    )
    return team 


async def run_interview(team):
    async for message in team.run_stream(task="Start the interview with the first quesiton?"):
        if isinstance(message , TaskResult):
             message = f"Interview complete with resutl: {message.stop_reason}"
             yield message 
            
        else:
            message= f"{message.source}:{message.content}"
            yield message

async def main():
    job_position = "AI Engineer"
    team = await my_agents(job_position)

    async for message in run_interview(team):
        print('-' * 70)
        print(message)




if __name__ == "__main__":
    import asyncio
    asyncio.run(main())