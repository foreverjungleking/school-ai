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

_SYSTEM_PROMPT = """Use tools for factual school and schedule data. Never invent
timetable assignments: CP-SAT is authoritative. Never claim a draft exists
without a successful tool result. Publishing is unavailable. Request one tool
at a time. If a schedule ID is missing, use get_current_demo_schedule or omit
the optional schedule_id so the service resolves the current demo schedule."""


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
        available_tools = _relevant_tools(message, self._mcp.tool_definitions)

        while True:
            tools = (
                available_tools
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
                        content=json.dumps(_compact_tool_execution(execution)),
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


def _compact_tool_execution(execution: ToolExecution) -> dict[str, Any]:
    payload = execution.model_dump(mode="json", exclude={"result"})
    payload["result"] = _compact_result(execution.result)
    return payload


def _compact_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    compact = dict(result)
    lessons = compact.pop("lessons", None)
    if isinstance(lessons, list):
        compact["lesson_count"] = len(lessons)
    version = compact.get("version")
    if isinstance(version, dict):
        compact["version"] = _compact_result(version)
    for name in ("unchanged", "added", "removed", "changed"):
        items = compact.pop(name, None)
        if isinstance(items, list):
            compact[f"{name}_count"] = len(items)
    return compact


def _relevant_tools(
    message: str, tools: tuple[ToolDefinition, ...]
) -> tuple[ToolDefinition, ...]:
    """Keep obvious requests small while preserving a safe general fallback."""

    text = message.lower()
    if "what can you help" in text or "what can you do" in text:
        return ()
    names: set[str] = set()
    for keyword, matching in (
        ("teacher", {"list_teachers"}),
        ("room", {"list_rooms"}),
        ("student", {"list_student_groups"}),
        ("group", {"list_student_groups"}),
        ("activit", {"list_activities"}),
        (
            "publish",
            {"get_current_demo_schedule", "get_schedule", "get_published_schedule"},
        ),
        (
            "timetable",
            {"get_current_demo_schedule", "get_schedule", "get_published_schedule"},
        ),
        (
            "schedule",
            {"get_current_demo_schedule", "get_schedule", "get_published_schedule"},
        ),
        ("version", {"get_current_demo_schedule", "get_schedule_version"}),
        ("compare", {"get_current_demo_schedule", "compare_schedule_versions"}),
        ("draft", {"get_current_demo_schedule", "create_schedule_draft"}),
        ("generate", {"get_current_demo_schedule", "create_schedule_draft"}),
    ):
        if keyword in text:
            names.update(matching)
    if not names:
        return tools
    return tuple(tool for tool in tools if tool.name in names)


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
