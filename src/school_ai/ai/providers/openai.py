"""OpenAI Responses API provider."""

import json
from typing import Any

import httpx

from school_ai.ai.models import ChatMessage, ProviderTurn, ToolCall, ToolDefinition
from school_ai.ai.providers.base import ProviderResponseError


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 60) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def generate(
        self, messages: tuple[ChatMessage, ...], tools: tuple[ToolDefinition, ...]
    ) -> ProviderTurn:
        payload = {
            "model": self._model,
            "input": [_openai_message(item) for item in messages],
            "tools": [_openai_tool(item) for item in tools],
            "tool_choice": "auto" if tools else "none",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            calls = tuple(
                ToolCall(name=item["name"], arguments=json.loads(item["arguments"]))
                for item in data.get("output", [])
                if item.get("type") == "function_call"
            )
            return ProviderTurn(text=_response_text(data), tool_calls=calls)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderResponseError("OpenAI returned an invalid response") from exc


def _openai_tool(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.input_schema,
        "strict": True,
    }


def _openai_message(message: ChatMessage) -> dict[str, str]:
    if message.role == "tool":
        return {"role": "user", "content": f"Tool result: {message.content}"}
    return {"role": message.role, "content": message.content}


def _response_text(data: dict[str, Any]) -> str:
    return "".join(
        content.get("text", "")
        for item in data.get("output", [])
        if item.get("type") == "message"
        for content in item.get("content", [])
        if content.get("type") == "output_text"
    )
