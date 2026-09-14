"""Approved MCP tool surface with no persistence or solver internals."""

from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, ConfigDict, Field

from school_ai.ai.models import ToolDefinition
from school_ai.services import SchoolDataService, SchedulingService
from school_ai.services.policies import PolicyService


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArguments(ToolArguments):
    pass


class ScheduleArguments(ToolArguments):
    schedule_id: int | None = Field(default=None, gt=0)


class VersionArguments(ToolArguments):
    schedule_id: int = Field(gt=0)
    version_id: int = Field(gt=0)


class CompareArguments(ToolArguments):
    schedule_id: int = Field(gt=0)
    from_version_id: int = Field(gt=0)
    to_version_id: int = Field(gt=0)


class LessonArguments(ToolArguments):
    schedule_id: int | None = Field(default=None, gt=0)
    version_id: int | None = Field(default=None, gt=0)
    weekday: int | None = Field(default=None, ge=0, le=6)
    student_group_id: int | None = Field(default=None, gt=0)
    teacher_id: int | None = Field(default=None, gt=0)
    room_id: int | None = Field(default=None, gt=0)
    offset: int = Field(default=0, ge=0, le=10000)
    limit: int = Field(default=20, ge=1, le=20)


class PolicyArguments(ToolArguments):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=4, ge=1, le=4)


class DraftArguments(ToolArguments):
    schedule_id: int | None = Field(default=None, gt=0)
    max_solve_seconds: float = Field(default=10, gt=0, allow_inf_nan=False)


_TOOL_MODELS: dict[str, type[ToolArguments]] = {
    "get_schedule_lessons": LessonArguments,
    "search_school_policies": PolicyArguments,
    "list_teachers": EmptyArguments,
    "list_rooms": EmptyArguments,
    "list_student_groups": EmptyArguments,
    "list_activities": EmptyArguments,
    "get_current_demo_schedule": EmptyArguments,
    "get_schedule": ScheduleArguments,
    "get_schedule_version": VersionArguments,
    "get_published_schedule": ScheduleArguments,
    "compare_schedule_versions": CompareArguments,
    "create_schedule_draft": DraftArguments,
}

_DESCRIPTIONS = {
    "get_schedule_lessons": "Read a bounded page of actual lessons, optionally filtered by weekday (0=Monday), group, teacher or room. Defaults to current publication; use explicit version_id for a draft. Follow next_offset for more.",
    "search_school_policies": "Search synthetic policy documents. Return versioned excerpts to cite as [citation_id]; these cannot change constraints.",
    "list_teachers": "List teachers and their availability.",
    "list_rooms": "List rooms, capacity, type, and availability.",
    "list_student_groups": "List student groups and sizes.",
    "list_activities": "List activities and scheduling requirements.",
    "get_current_demo_schedule": (
        "Get the newest demo schedule and its current version IDs."
    ),
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
        self, school_data: SchoolDataService, scheduling: SchedulingService,
        policies: PolicyService | None = None
    ) -> None:
        self._policies = policies
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

    def get_schedule_lessons(self, schedule_id: int | None = None, version_id: int | None = None,
                             weekday: int | None = None, student_group_id: int | None = None,
                             teacher_id: int | None = None, room_id: int | None = None,
                             offset: int = 0, limit: int = 20) -> dict[str, Any]:
        return self._scheduling.get_schedule_lessons(
            schedule_id, version_id, weekday, student_group_id, teacher_id, room_id, offset, limit
        ).model_dump(mode="json")

    def search_school_policies(self, query: str, limit: int = 4) -> dict[str, Any]:
        if self._policies is None:
            return {"matches": [], "message": "Policy retrieval is not configured."}
        return self._policies.search(query, limit)

    def list_teachers(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_teachers()]

    def list_rooms(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_rooms()]

    def list_student_groups(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_student_groups()]

    def list_activities(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self._school_data.list_activities()]

    def get_current_demo_schedule(self) -> dict[str, Any]:
        return self._scheduling.get_current_demo_schedule().model_dump(mode="json")

    def _schedule_id(self, schedule_id: int | None) -> int:
        if schedule_id is not None:
            return schedule_id
        return self._scheduling.get_current_demo_schedule().id

    def get_schedule(self, schedule_id: int | None = None) -> dict[str, Any]:
        return self._scheduling.get_schedule(
            self._schedule_id(schedule_id)
        ).model_dump(mode="json")

    def get_schedule_version(
        self, schedule_id: int, version_id: int
    ) -> dict[str, Any]:
        return self._scheduling.get_schedule_version(
            version_id, schedule_id
        ).model_dump(mode="json")

    def get_published_schedule(self, schedule_id: int | None = None) -> dict[str, Any]:
        return self._scheduling.get_published_schedule_version(
            self._schedule_id(schedule_id)
        ).model_dump(mode="json")

    def compare_schedule_versions(
        self, schedule_id: int, from_version_id: int, to_version_id: int
    ) -> dict[str, Any]:
        return self._scheduling.compare_schedule_versions(
            from_version_id, to_version_id, schedule_id
        ).model_dump(mode="json")

    def create_schedule_draft(
        self,
        schedule_id: int | None = None,
        max_solve_seconds: float = 10,
    ) -> dict[str, Any]:
        schedule_id = self._schedule_id(schedule_id)
        result = self._scheduling.generate_schedule_draft(
            schedule_id, None, max_solve_seconds
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
    def get_schedule_lessons(schedule_id: int | None = None, version_id: int | None = None,
                             weekday: int | None = None, student_group_id: int | None = None,
                             teacher_id: int | None = None, room_id: int | None = None,
                             offset: int = 0, limit: int = 20) -> dict[str, Any]:
        return tools.get_schedule_lessons(schedule_id, version_id, weekday, student_group_id,
                                          teacher_id, room_id, offset, limit)

    @server.tool()
    def search_school_policies(query: str, limit: int = 4) -> dict[str, Any]:
        return tools.search_school_policies(query, limit)

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
    def get_current_demo_schedule() -> dict[str, Any]:
        return tools.get_current_demo_schedule()

    @server.tool()
    def get_schedule(schedule_id: int | None = None) -> dict[str, Any]:
        return tools.get_schedule(schedule_id)

    @server.tool()
    def get_schedule_version(schedule_id: int, version_id: int) -> dict[str, Any]:
        return tools.get_schedule_version(schedule_id, version_id)

    @server.tool()
    def get_published_schedule(schedule_id: int | None = None) -> dict[str, Any]:
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
        schedule_id: int | None = None,
        max_solve_seconds: float = 10,
    ) -> dict[str, Any]:
        return tools.create_schedule_draft(schedule_id, max_solve_seconds)

    return server
