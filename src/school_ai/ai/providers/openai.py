"""OpenAI Responses API provider."""

import json
import logging
from typing import Any

import httpx

from school_ai.ai.models import ChatMessage, ProviderTurn, ToolCall, ToolDefinition
from school_ai.ai.providers.base import ProviderConfigurationError, ProviderResponseError


logger = logging.getLogger(__name__)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 60) -> None:
        if not api_key.strip():
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is required when AI_PROVIDER=openai"
            )
        if not model.strip():
            raise ProviderConfigurationError(
                "OPENAI_MODEL is required when AI_PROVIDER=openai"
            )
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
            "parallel_tool_calls": False,
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
            calls = _tool_calls(data)
            return ProviderTurn(text=_response_text(data), tool_calls=calls)
        except httpx.HTTPStatusError as exc:
            diagnostics = _error_diagnostics(exc.response)
            logger.warning(
                "OpenAI Responses API rejected request: status=%s error_type=%s "
                "error_code=%s error_param=%s",
                exc.response.status_code,
                diagnostics["type"],
                diagnostics["code"],
                diagnostics["param"],
            )
            raise ProviderResponseError(
                _status_error_message(exc.response.status_code)
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "OpenAI Responses API transport failure: error=%s",
                type(exc).__name__,
            )
            raise ProviderResponseError("OpenAI request failed") from exc
        except (
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning(
                "OpenAI Responses API returned malformed data: error=%s",
                type(exc).__name__,
            )
            raise ProviderResponseError("OpenAI returned an invalid response") from exc


def _openai_tool(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.input_schema,
        "strict": False,
    }


def _openai_message(message: ChatMessage) -> dict[str, str]:
    if message.role == "tool":
        return {"role": "user", "content": f"Tool result: {message.content}"}
    return {"role": message.role, "content": message.content}


def _response_text(data: dict[str, Any]) -> str:
    output = _response_output(data)
    return "".join(
        content.get("text", "")
        for item in output
        if item.get("type") == "message"
        for content in item.get("content", [])
        if content.get("type") == "output_text"
    )


def _tool_calls(data: dict[str, Any]) -> tuple[ToolCall, ...]:
    calls: list[ToolCall] = []
    for item in _response_output(data):
        if item.get("type") != "function_call":
            continue
        arguments = json.loads(item["arguments"])
        if not isinstance(arguments, dict):
            raise TypeError("function call arguments must decode to an object")
        calls.append(ToolCall(name=item["name"], arguments=arguments))
    return tuple(calls)


def _response_output(data: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise TypeError("response must be an object")
    output = data.get("output")
    if not isinstance(output, list) or not all(
        isinstance(item, dict) for item in output
    ):
        raise TypeError("response output must be a list of objects")
    return output


def _error_diagnostics(response: httpx.Response) -> dict[str, Any]:
    diagnostics = {"type": None, "code": None, "param": None}
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        return diagnostics
    if not isinstance(data, dict) or not isinstance(data.get("error"), dict):
        return diagnostics
    error = data["error"]
    for field in diagnostics:
        value = error.get(field)
        if isinstance(value, (str, int, float, bool)) or value is None:
            diagnostics[field] = value
    return diagnostics


def _status_error_message(status_code: int) -> str:
    if status_code == 400:
        return "OpenAI rejected the request"
    if status_code == 401:
        return "OpenAI authentication failed"
    if status_code == 403:
        return "OpenAI permission denied"
    if status_code == 429:
        return "OpenAI rate limit or quota exceeded"
    if status_code >= 500:
        return "OpenAI service failed"
    return "OpenAI request failed"
