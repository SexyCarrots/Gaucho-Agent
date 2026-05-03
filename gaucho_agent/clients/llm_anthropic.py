"""Anthropic LLM client wrapper – normalizes to OpenAI tool-call format."""

from __future__ import annotations

import json
from typing import Any

import anthropic


class AnthropicClient:
    """Wrapper around the Anthropic Messages API.

    Accepts OpenAI-style tool schemas and messages, normalizes internally,
    and returns a response dict in the same shape as OpenAIClient.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    # ------------------------------------------------------------------
    # Format converters
    # ------------------------------------------------------------------

    @staticmethod
    def _to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI function-calling schema to Anthropic tool schema."""
        result = []
        for t in tools:
            fn = t.get("function", {})
            result.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return result

    @staticmethod
    def _to_anthropic_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Split system prompt from conversation messages."""
        system: str | None = None
        converted: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                system = msg.get("content", "")
                continue
            if role == "tool":
                # OpenAI tool result → Anthropic user message with tool_result block
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": msg.get("content", ""),
                            }
                        ],
                    }
                )
                continue
            converted.append({"role": role, "content": msg.get("content", "")})
        return system, converted

    @staticmethod
    def _normalize_response(message: anthropic.types.Message) -> dict[str, Any]:
        """Convert Anthropic response to OpenAI-style assistant dict."""
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in message.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )

        return {
            "role": "assistant",
            "content": "\n".join(text_parts),
            "tool_calls": tool_calls,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send messages to Anthropic and return normalized assistant turn."""
        system, converted = self._to_anthropic_messages(messages)
        anthropic_tools = self._to_anthropic_tools(tools) if tools else []

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": converted,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = self._client.messages.create(**kwargs)
        return self._normalize_response(response)
