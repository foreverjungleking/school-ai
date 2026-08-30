"""Ollama chat/tool-calling provider."""

import json
from typing import Any

import httpx

from school_ai.ai.models import ChatMessage, ProviderTurn, ToolCall, ToolDefinition
from school_ai.ai.providers.base import ProviderResponseError

_JSON_PROTOCOL = """When you do not emit a native tool call, respond with exactly
one JSON object matching {"tool_calls": [], "text": "your answer"}. To request
a tool without native calling, put one {"name": "...", "arguments": {...}}
inside tool_calls and leave text empty. Do not use Markdown fences."""


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 60) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def generate(
        self, messages: tuple[ChatMessage, ...], tools: tuple[ToolDefinition, ...]
    ) -> ProviderTurn:
        try:
            if tools:
                message = await self._chat(
                    {
                        "model": self._model,
                        "stream": False,
                        "messages": [_ollama_message(item) for item in messages],
                        "tools": [_ollama_tool(item) for item in tools],
                        "options": {"temperature": 0},
                    }
                )
                calls = _native_tool_calls(message)
                if calls:
                    return ProviderTurn(
                        text=message.get("content", ""), tool_calls=calls
                    )
                content = message.get("content", "")
                try:
                    return ProviderTurn.model_validate_json(content)
                except ValueError:
                    if content.strip() and any(
                        item.role == "tool" for item in messages
                    ):
                        return ProviderTurn(text=content)

            protocol = _JSON_PROTOCOL
            if tools:
                protocol += "\nApproved tools:\n" + json.dumps(
                    [_ollama_tool(item)["function"] for item in tools]
                )
            message = await self._chat(
                {
                    "model": self._model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": protocol},
                        *[_ollama_message(item) for item in messages],
                    ],
                    "format": _structured_response_schema(),
                    "options": {"temperature": 0},
                }
            )
            return ProviderTurn.model_validate_json(message.get("content", ""))
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError("Ollama returned an invalid response") from exc

    async def _chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()["message"]


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


def _tool_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise TypeError("tool arguments must be an object")
    return value


def _native_tool_calls(message: dict[str, Any]) -> tuple[ToolCall, ...]:
    return tuple(
        ToolCall(
            name=item["function"]["name"],
            arguments=_tool_arguments(item["function"].get("arguments", {})),
        )
        for item in message.get("tool_calls", [])
    )


def _structured_response_schema() -> dict[str, Any]:
    schema = ProviderTurn.model_json_schema()
    schema["required"] = ["text", "tool_calls"]
    tool_call = schema.get("$defs", {}).get("ToolCall")
    if isinstance(tool_call, dict):
        tool_call["required"] = ["name", "arguments"]
    return schema
