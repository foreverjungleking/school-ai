"""Minimal, bounded LLM → MCP tool orchestration."""

import json
from typing import Any

from pydantic import ValidationError

from school_ai.ai.models import (
    ChatMessage,
    ChatResult,
    ProviderTurn,
    ToolDefinition,
    ToolExecution,
)
from school_ai.ai.providers.base import LLMProvider, ProviderResponseError
from school_ai.mcp.client import MCPClient
from school_ai.mcp.server import ToolNotAllowedError

_SYSTEM_PROMPT = """You are the School AI assistant. Use only the supplied tools.
CP-SAT is authoritative. Never invent lessons or claim a draft exists unless the
tool result contains a version. Publishing is unavailable and must remain a
deliberate user action in the normal UI/API. Do not propose SQL or constraint
relaxation. Request at most one approved tool at a time."""


class HarnessError(RuntimeError):
    pass


class AIHarness:
    def __init__(
        self,
        provider: LLMProvider,
        mcp: MCPClient,
        max_tool_iterations: int = 4,
    ) -> None:
        if not 1 <= max_tool_iterations <= 5:
            raise ValueError("max_tool_iterations must be between 1 and 5")
        self._provider = provider
        self._mcp = mcp
        self._max_tool_iterations = max_tool_iterations

    async def chat(self, message: str) -> ChatResult:
        if not message.strip():
            raise ValueError("message must not be blank")
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=message.strip()),
        ]
        executions: list[ToolExecution] = []

        while True:
            tools = (
                self._mcp.tool_definitions
                if len(executions) < self._max_tool_iterations
                else ()
            )
            turn = await self._provider_turn(tuple(messages), tools)
            if len(turn.tool_calls) > 1:
                raise HarnessError("AI provider requested too many tools in one turn")
            if not turn.tool_calls:
                text = turn.text.strip()
                if not text:
                    if executions:
                        raise HarnessError("AI provider returned an empty summary")
                    text = "I could not determine a safe action."
                return ChatResult(
                    assistant_text=text,
                    tool_calls=tuple(executions),
                    metadata=_result_metadata(self._provider.name, executions),
                )

            if len(executions) >= self._max_tool_iterations:
                raise HarnessError("AI provider exceeded the tool iteration limit")

            call = turn.tool_calls[0]
            execution = self._execute_tool(call.name, call.arguments)
            executions.append(execution)

            failure_text = _authoritative_draft_failure(execution)
            if failure_text:
                return ChatResult(
                    assistant_text=failure_text,
                    tool_calls=tuple(executions),
                    metadata=_result_metadata(self._provider.name, executions),
                )
            if not execution.success:
                return ChatResult(
                    assistant_text=f"The {execution.name} tool failed: {execution.error}",
                    tool_calls=tuple(executions),
                    metadata=_result_metadata(self._provider.name, executions),
                )

            if turn.text.strip():
                messages.append(ChatMessage(role="assistant", content=turn.text.strip()))
            messages.extend(
                (
                    ChatMessage(
                        role="tool",
                        content=json.dumps(execution.model_dump(mode="json")),
                    ),
                    ChatMessage(
                        role="user",
                        content=(
                            "Use another approved tool only if needed; otherwise "
                            "summarize the results accurately."
                        ),
                    ),
                )
            )

    async def _provider_turn(
        self,
        messages: tuple[ChatMessage, ...],
        tools: tuple[ToolDefinition, ...],
    ) -> ProviderTurn:
        try:
            return ProviderTurn.model_validate(
                await self._provider.generate(messages, tools)
            )
        except (ValidationError, TypeError, ProviderResponseError) as exc:
            raise HarnessError("AI provider returned an invalid response") from exc

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolExecution:
        try:
            result = self._mcp.call_tool(name, arguments)
            return ToolExecution(
                name=name,
                arguments=arguments,
                success=True,
                result=result,
            )
        except ToolNotAllowedError as exc:
            raise HarnessError("AI provider requested an unauthorized tool") from exc
        except (LookupError, ValueError) as exc:
            return ToolExecution(
                name=name,
                arguments=arguments,
                success=False,
                error=str(exc),
            )


def _result_metadata(
    provider: str, executions: list[ToolExecution]
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "provider": provider,
        "tool_iterations": len(executions),
        "draft_created": any(_draft_created(item) for item in executions),
    }
    for execution in reversed(executions):
        if not isinstance(execution.result, dict):
            continue
        result = execution.result
        version = result.get("version")
        if isinstance(version, dict):
            metadata.setdefault("version_id", version.get("id"))
            metadata.setdefault("schedule_id", version.get("schedule_id"))
        elif "version_number" in result:
            metadata.setdefault("version_id", result.get("id"))
            metadata.setdefault("schedule_id", result.get("schedule_id"))
        if result.get("solver_status") is not None:
            metadata.setdefault("solver_status", result["solver_status"])
    return {key: value for key, value in metadata.items() if value is not None}


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
