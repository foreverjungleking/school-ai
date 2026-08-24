"""Minimal, bounded LLM → MCP tool orchestration."""

import json

from pydantic import ValidationError

from school_ai.ai.models import (
    ChatMessage,
    ChatResult,
    ProviderTurn,
    ToolExecution,
)
from school_ai.ai.providers.base import LLMProvider, ProviderResponseError
from school_ai.mcp.client import MCPClient
from school_ai.mcp.server import ToolNotAllowedError

_SYSTEM_PROMPT = """You are the School AI assistant. Use only the supplied tools.
CP-SAT is authoritative. Never invent lessons or claim a draft exists unless the
tool result contains a version. Publishing is unavailable and must remain a
deliberate user action in the normal UI/API. Do not propose SQL or constraint
relaxation. Select at most one tool per turn."""


class HarnessError(RuntimeError):
    pass


class AIHarness:
    def __init__(self, provider: LLMProvider, mcp: MCPClient) -> None:
        self._provider = provider
        self._mcp = mcp

    async def chat(self, message: str) -> ChatResult:
        if not message.strip():
            raise ValueError("message must not be blank")
        try:
            turn = ProviderTurn.model_validate(
                await self._provider.generate(
                    (
                        ChatMessage(role="system", content=_SYSTEM_PROMPT),
                        ChatMessage(role="user", content=message.strip()),
                    ),
                    self._mcp.tool_definitions,
                )
            )
        except (ValidationError, TypeError, ProviderResponseError) as exc:
            raise HarnessError("AI provider returned an invalid response") from exc
        if len(turn.tool_calls) > 1:
            raise HarnessError("AI provider requested too many tools")
        if not turn.tool_calls:
            return ChatResult(
                assistant_text=turn.text.strip() or "I could not determine a safe action."
            )

        call = turn.tool_calls[0]
        try:
            result = self._mcp.call_tool(call.name, call.arguments)
            execution = ToolExecution(
                name=call.name,
                arguments=call.arguments,
                success=True,
                result=result,
            )
        except ToolNotAllowedError as exc:
            raise HarnessError("AI provider requested an unauthorized tool") from exc
        except (LookupError, ValueError) as exc:
            execution = ToolExecution(
                name=call.name,
                arguments=call.arguments,
                success=False,
                error=str(exc),
            )

        failure_text = _authoritative_draft_failure(execution)
        if failure_text:
            return ChatResult(
                assistant_text=failure_text,
                tool_calls=(execution,),
                metadata={"draft_created": False},
            )
        if not execution.success:
            return ChatResult(
                assistant_text=f"The {execution.name} tool failed: {execution.error}",
                tool_calls=(execution,),
            )

        summary_messages = (
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=message.strip()),
            ChatMessage(
                role="tool",
                content=json.dumps(execution.model_dump(mode="json")),
            ),
            ChatMessage(
                role="user",
                content="Summarize the tool result accurately. Do not call another tool.",
            ),
        )
        try:
            summary = ProviderTurn.model_validate(
                await self._provider.generate(summary_messages, ())
            )
        except (ValidationError, TypeError, ProviderResponseError) as exc:
            raise HarnessError("AI provider returned an invalid summary") from exc
        if summary.tool_calls:
            raise HarnessError("AI provider attempted an unauthorized follow-up tool")
        text = summary.text.strip()
        if not text:
            raise HarnessError("AI provider returned an empty summary")
        return ChatResult(
            assistant_text=text,
            tool_calls=(execution,),
            metadata={"draft_created": _draft_created(execution)},
        )


def _draft_created(execution: ToolExecution) -> bool:
    return bool(
        execution.name == "create_schedule_draft"
        and execution.success
        and isinstance(execution.result, dict)
        and execution.result.get("version")
    )


def _authoritative_draft_failure(execution: ToolExecution) -> str | None:
    if execution.name != "create_schedule_draft":
        return None
    if not execution.success:
        return f"No draft was created: {execution.error}"
    if not isinstance(execution.result, dict):
        return "No draft was created because the scheduler returned an invalid result."
    status = execution.result.get("solver_status")
    if status in {"INFEASIBLE", "UNKNOWN"} or not execution.result.get("version"):
        return f"CP-SAT returned {status or 'no valid schedule'}; no draft was created."
    return None
