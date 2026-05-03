"""API route for LLM chat with tool calling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from gaucho_agent.config import settings
from gaucho_agent.db import get_session as _get_session
from gaucho_agent.services.tool_executor import TOOL_SCHEMAS, execute_tool

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, Any]] = []


def _session():
    with _get_session() as s:
        yield s


def _get_llm_client():
    if settings.llm_provider == "anthropic":
        from gaucho_agent.clients.llm_anthropic import AnthropicClient
        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.llm_model)
    from gaucho_agent.clients.llm_openai import OpenAIClient
    return OpenAIClient(api_key=settings.openai_api_key, model=settings.llm_model)


def _load_system_prompt() -> str:
    path = Path(__file__).parent.parent / "prompts" / "system.txt"
    if path.exists():
        return path.read_text()
    return "You are a UCSB academic assistant."


@router.post("/chat")
def chat(req: ChatRequest, session: Session = Depends(_session)):
    """Run a single chat turn with tool calling."""
    llm = _get_llm_client()
    system_prompt = _load_system_prompt()

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    # Agentic loop
    tool_calls_made: list[dict[str, Any]] = []
    while True:
        response = llm.chat_with_tools(messages, TOOL_SCHEMAS)
        tool_calls = response.get("tool_calls") or []

        if not tool_calls:
            break

        messages.append(response)
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            try:
                args = json.loads(fn["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {}

            tool_result = execute_tool(name, args, session)
            tool_calls_made.append({"tool": name, "args": args, "result": tool_result})

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": json.dumps(tool_result),
            })

    return {
        "reply": response.get("content") or "",
        "tool_calls": tool_calls_made,
    }
