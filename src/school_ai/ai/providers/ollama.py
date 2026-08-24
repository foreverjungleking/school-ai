"""Ollama chat/tool-calling provider."""

from typing import Any

import httpx

from school_ai.ai.models import ChatMessage, ProviderTurn, ToolCall, ToolDefinition
from school_ai.ai.providers.base import ProviderResponseError


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 60) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def generate(
        self, messages: tuple[ChatMessage, ...], tools: tuple[ToolDefinition, ...]
    ) -> ProviderTurn:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [_ollama_message(item) for item in messages],
            "tools": [_ollama_tool(item) for item in tools],
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
            message = data["message"]
            calls = tuple(
                ToolCall(
                    name=item["function"]["name"],
                    arguments=item["function"].get("arguments", {}),
                )
                for item in message.get("tool_calls", [])
            )
            return ProviderTurn(text=message.get("content", ""), tool_calls=calls)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError("Ollama returned an invalid response") from exc


def _ollama_tool(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


def _ollama_message(message: ChatMessage) -> dict[str, str]:
    if message.role == "tool":
        return {"role": "user", "content": f"Tool result: {message.content}"}
    return {"role": message.role, "content": message.content}
