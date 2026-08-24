"""Approved MCP tool surface with no persistence or solver internals."""

from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, ConfigDict, Field

from school_ai.ai.models import ToolDefinition
from school_ai.services import SchoolDataService, SchedulingService
from school_ai.solver import TimeSlot


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArguments(ToolArguments):
    pass


class ScheduleArguments(ToolArguments):
    schedule_id: int = Field(gt=0)


class VersionArguments(ToolArguments):
    schedule_id: int = Field(gt=0)
    version_id: int = Field(gt=0)


class CompareArguments(ToolArguments):
    schedule_id: int = Field(gt=0)
    from_version_id: int = Field(gt=0)
    to_version_id: int = Field(gt=0)


class DraftArguments(ToolArguments):
    schedule_id: int = Field(gt=0)
    time_slots: tuple[TimeSlot, ...] = Field(min_length=1)
    max_solve_seconds: float = Field(default=10, gt=0, allow_inf_nan=False)


_TOOL_MODELS: dict[str, type[ToolArguments]] = {
    "list_teachers": EmptyArguments,
    "list_rooms": EmptyArguments,
    "list_student_groups": EmptyArguments,
    "list_activities": EmptyArguments,
    "get_schedule": ScheduleArguments,
    "get_schedule_version": VersionArguments,
    "get_published_schedule": ScheduleArguments,
    "compare_schedule_versions": CompareArguments,
    "create_schedule_draft": DraftArguments,
}

_DESCRIPTIONS = {
    "list_teachers": "List teachers and their availability.",
    "list_rooms": "List rooms, capacity, type, and availability.",
    "list_student_groups": "List student groups and sizes.",
    "list_activities": "List activities and scheduling requirements.",
    "get_schedule": "Get a logical schedule summary by ID.",
    "get_schedule_version": "Get a complete stored schedule version.",
    "get_published_schedule": "Get the currently published version for a schedule.",
    "compare_schedule_versions": "Compare two stored versions of one schedule.",
    "create_schedule_draft": "Run CP-SAT and persist a DRAFT; never publishes it.",
}


class ToolNotAllowedError(ValueError):
    pass


class SchoolMCPServer:
    """MCP-facing adapter that delegates exclusively to application services."""

    def __init__(
        self, school_data: SchoolDataService, scheduling: SchedulingService
    ) -> None:
        self._school_data = school_data
        self._scheduling = scheduling

    @property
    def tool_definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(
            ToolDefinition(
                name=name,
                description=_DESCRIPTIONS[name],
                input_schema=model.model_json_schema(),
            )
            for name, model in _TOOL_MODELS.items()
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        argument_model = _TOOL_MODELS.get(name)
        if argument_model is None:
            raise ToolNotAllowedError(f"tool '{name}' is not allowed")
        parsed = argument_model.model_validate(arguments)
        method = getattr(self, name)
        return method(**parsed.model_dump())

    def list_teachers(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_teachers()]

    def list_rooms(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_rooms()]

    def list_student_groups(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_student_groups()]

    def list_activities(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_activities()]

    def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        return self._scheduling.get_schedule(schedule_id).model_dump(mode="json")

    def get_schedule_version(
        self, schedule_id: int, version_id: int
    ) -> dict[str, Any]:
        return self._scheduling.get_schedule_version(
            version_id, schedule_id
        ).model_dump(mode="json")

    def get_published_schedule(self, schedule_id: int) -> dict[str, Any]:
        return self._scheduling.get_published_schedule_version(schedule_id).model_dump(
            mode="json"
        )

    def compare_schedule_versions(
        self, schedule_id: int, from_version_id: int, to_version_id: int
    ) -> dict[str, Any]:
        return self._scheduling.compare_schedule_versions(
            from_version_id, to_version_id, schedule_id
        ).model_dump(mode="json")

    def create_schedule_draft(
        self,
        schedule_id: int,
        time_slots: tuple[TimeSlot, ...],
        max_solve_seconds: float = 10,
    ) -> dict[str, Any]:
        result = self._scheduling.generate_schedule_draft(
            schedule_id, time_slots, max_solve_seconds
        )
        return result.model_dump(mode="json")


def create_mcp_sdk_server(tools: SchoolMCPServer) -> MCPServer:
    """Expose approved adapters through the official MCP server SDK."""

    server = MCPServer(
        "School AI",
        instructions=(
            "Use only these application-service tools. Draft generation is CP-SAT "
            "backed. Publishing is intentionally unavailable."
        ),
    )

    @server.tool()
    def list_teachers() -> list[dict[str, Any]]:
        return tools.list_teachers()

    @server.tool()
    def list_rooms() -> list[dict[str, Any]]:
        return tools.list_rooms()

    @server.tool()
    def list_student_groups() -> list[dict[str, Any]]:
        return tools.list_student_groups()

    @server.tool()
    def list_activities() -> list[dict[str, Any]]:
        return tools.list_activities()

    @server.tool()
    def get_schedule(schedule_id: int) -> dict[str, Any]:
        return tools.get_schedule(schedule_id)

    @server.tool()
    def get_schedule_version(schedule_id: int, version_id: int) -> dict[str, Any]:
        return tools.get_schedule_version(schedule_id, version_id)

    @server.tool()
    def get_published_schedule(schedule_id: int) -> dict[str, Any]:
        return tools.get_published_schedule(schedule_id)

    @server.tool()
    def compare_schedule_versions(
        schedule_id: int, from_version_id: int, to_version_id: int
    ) -> dict[str, Any]:
        return tools.compare_schedule_versions(
            schedule_id, from_version_id, to_version_id
        )

    @server.tool()
    def create_schedule_draft(
        schedule_id: int,
        time_slots: list[dict[str, Any]],
        max_solve_seconds: float = 10,
    ) -> dict[str, Any]:
        parsed = tuple(TimeSlot.model_validate(item) for item in time_slots)
        return tools.create_schedule_draft(
            schedule_id, parsed, max_solve_seconds
        )

    return server
