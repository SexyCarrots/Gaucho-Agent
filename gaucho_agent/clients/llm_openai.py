"""OpenAI LLM client wrapper."""

from __future__ import annotations

from typing import Any

import httpx


class OpenAIClient:
    """Thin wrapper around the OpenAI chat completions API."""

    _BASE = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send a chat completion request and return a normalized assistant turn."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        with httpx.Client(timeout=60.0) as client:
            response = client.post(self._BASE, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]["message"]
        return {
            "role": "assistant",
            "content": choice.get("content") or "",
            "tool_calls": choice.get("tool_calls") or [],
        }
