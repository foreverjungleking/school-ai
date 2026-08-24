import asyncio
from datetime import datetime, time, timezone
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from school_ai.ai.harness import AIHarness, HarnessError
from school_ai.ai.models import ProviderTurn, ToolCall
from school_ai.ai.providers.fake import FakeProvider
from school_ai.ai.providers.factory import create_provider
from school_ai.ai.providers.base import ProviderConfigurationError
from school_ai.ai.providers.ollama import OllamaProvider
from school_ai.ai.providers.openai import OpenAIProvider
from school_ai.api.app import create_app
from school_ai.api.dependencies import get_ai_harness
from school_ai.config import Settings
from school_ai.database.models import ScheduleVersionStatus
from school_ai.mcp.client import InProcessMCPClient
from school_ai.mcp.server import SchoolMCPServer, create_mcp_sdk_server
from school_ai.services import SchoolDataService, SchedulingService
from school_ai.services.dto import GenerateScheduleResult, ScheduleVersionView
from school_ai.services.school_data import TeacherView
from school_ai.solver import SolveStatus, TimeSlot


def _version() -> ScheduleVersionView:
    return ScheduleVersionView(
        id=11,
        schedule_id=7,
        version_number=2,
        status=ScheduleVersionStatus.DRAFT,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        published_at=None,
        solver_status=SolveStatus.OPTIMAL,
        solve_duration_seconds=0.2,
        solver_metadata={},
        lessons=(),
    )


def _services() -> tuple[Mock, Mock]:
    school_data = Mock(spec=SchoolDataService)
    school_data.list_teachers.return_value = (
        TeacherView(id=1, name="Ms Lim", availability=()),
    )
    school_data.list_rooms.return_value = ()
    school_data.list_student_groups.return_value = ()
    school_data.list_activities.return_value = ()
    scheduling = Mock(spec=SchedulingService)
    scheduling.get_published_schedule_version.return_value = _version()
    scheduling.generate_schedule_draft.return_value = GenerateScheduleResult(
        solver_status=SolveStatus.OPTIMAL,
        solve_duration_seconds=0.2,
        version=_version(),
        solver_metadata={},
        message="draft schedule version created",
    )
    return school_data, scheduling


def _draft_arguments() -> dict[str, Any]:
    return {
        "schedule_id": 7,
        "time_slots": [
            {
                "id": 1,
                "weekday": 0,
                "start_time": "08:00:00",
                "end_time": "09:00:00",
            }
        ],
    }


def _client(school_data: Mock, scheduling: Mock) -> InProcessMCPClient:
    return InProcessMCPClient(SchoolMCPServer(school_data, scheduling))


def test_mcp_list_teachers_calls_application_service() -> None:
    school_data, scheduling = _services()
    server = SchoolMCPServer(school_data, scheduling)

    result = server.list_teachers()

    school_data.list_teachers.assert_called_once_with()
    assert result == [{"id": 1, "name": "Ms Lim", "availability": []}]


def test_mcp_get_published_schedule_calls_application_service() -> None:
    school_data, scheduling = _services()
    server = SchoolMCPServer(school_data, scheduling)

    result = server.get_published_schedule(7)

    scheduling.get_published_schedule_version.assert_called_once_with(7)
    assert result["id"] == 11


def test_mcp_create_draft_calls_application_service() -> None:
    school_data, scheduling = _services()
    server = SchoolMCPServer(school_data, scheduling)
    slot = TimeSlot(id=1, weekday=0, start_time=time(8), end_time=time(9))

    result = server.create_schedule_draft(7, (slot,), 3)

    scheduling.generate_schedule_draft.assert_called_once_with(7, (slot,), 3)
    assert result["version"]["id"] == 11


def test_official_mcp_server_exposes_only_approved_tools() -> None:
    school_data, scheduling = _services()
    sdk_server = create_mcp_sdk_server(SchoolMCPServer(school_data, scheduling))

    names = {item.name for item in asyncio.run(sdk_server.list_tools())}

    assert names == {
        "list_teachers",
        "list_rooms",
        "list_student_groups",
        "list_activities",
        "get_schedule",
        "get_schedule_version",
        "get_published_schedule",
        "compare_schedule_versions",
        "create_schedule_draft",
    }
    assert "publish_schedule" not in names


def test_harness_provider_is_replaceable_and_can_call_read_tool() -> None:
    school_data, scheduling = _services()
    provider = FakeProvider(
        ProviderTurn(tool_calls=(ToolCall(name="list_teachers"),)),
        ProviderTurn(text="There is one teacher: Ms Lim."),
    )
    harness = AIHarness(provider, _client(school_data, scheduling))

    result = asyncio.run(harness.chat("Show teachers"))

    assert result.assistant_text == "There is one teacher: Ms Lim."
    assert result.tool_calls[0].name == "list_teachers"
    assert len(provider.calls[0][1]) == 9


def test_fake_provider_can_request_published_schedule() -> None:
    school_data, scheduling = _services()
    provider = FakeProvider(
        ProviderTurn(
            tool_calls=(
                ToolCall(name="get_published_schedule", arguments={"schedule_id": 7}),
            )
        ),
        ProviderTurn(text="Schedule 7 has published version 2."),
    )

    result = asyncio.run(
        AIHarness(provider, _client(school_data, scheduling)).chat(
            "Show the published schedule"
        )
    )

    scheduling.get_published_schedule_version.assert_called_once_with(7)
    assert result.metadata["provider"] == "fake"
    assert result.metadata["version_id"] == 11


def test_harness_can_request_cp_sat_draft() -> None:
    school_data, scheduling = _services()
    provider = FakeProvider(
        ProviderTurn(
            tool_calls=(
                ToolCall(name="create_schedule_draft", arguments=_draft_arguments()),
            )
        ),
        ProviderTurn(text="CP-SAT created draft version 2."),
    )
    harness = AIHarness(provider, _client(school_data, scheduling))

    result = asyncio.run(harness.chat("Generate a draft for schedule 7"))

    assert result.metadata["draft_created"] is True
    scheduling.generate_schedule_draft.assert_called_once()


@pytest.mark.parametrize("status", [SolveStatus.INFEASIBLE, SolveStatus.UNKNOWN])
def test_harness_never_fabricates_failed_solver_result(status: SolveStatus) -> None:
    school_data, scheduling = _services()
    scheduling.generate_schedule_draft.return_value = GenerateScheduleResult(
        solver_status=status,
        solve_duration_seconds=0.2,
        solver_metadata={},
        message="solver did not produce a valid schedule",
    )
    provider = FakeProvider(
        ProviderTurn(
            tool_calls=(
                ToolCall(name="create_schedule_draft", arguments=_draft_arguments()),
            )
        )
    )
    harness = AIHarness(provider, _client(school_data, scheduling))

    result = asyncio.run(harness.chat("Generate a draft"))

    assert status.value in result.assistant_text
    assert result.metadata["draft_created"] is False
    assert len(provider.calls) == 1


@pytest.mark.parametrize("name", ["publish_schedule", "execute_sql", "unknown"])
def test_harness_rejects_unapproved_tools(name: str) -> None:
    school_data, scheduling = _services()
    provider = FakeProvider(ProviderTurn(tool_calls=(ToolCall(name=name),)))
    harness = AIHarness(provider, _client(school_data, scheduling))

    with pytest.raises(HarnessError, match="unauthorized"):
        asyncio.run(harness.chat("Do something unsafe"))


def test_harness_handles_malformed_provider_output() -> None:
    school_data, scheduling = _services()
    provider = FakeProvider({"tool_calls": "not-a-list"})
    harness = AIHarness(provider, _client(school_data, scheduling))

    with pytest.raises(HarnessError, match="invalid response"):
        asyncio.run(harness.chat("Show teachers"))


def test_harness_enforces_tool_iteration_limit() -> None:
    school_data, scheduling = _services()
    requested = ProviderTurn(tool_calls=(ToolCall(name="list_teachers"),))
    provider = FakeProvider(requested, requested, requested)
    harness = AIHarness(
        provider, _client(school_data, scheduling), max_tool_iterations=2
    )

    with pytest.raises(HarnessError, match="iteration limit"):
        asyncio.run(harness.chat("Keep listing teachers"))

    assert school_data.list_teachers.call_count == 2
    assert provider.calls[-1][1] == ()


def test_missing_provider_configuration_is_clear(monkeypatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    with pytest.raises(ProviderConfigurationError, match="AI_PROVIDER"):
        create_provider()


def test_provider_factory_selects_ollama_without_network_access(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")

    assert isinstance(create_provider(), OllamaProvider)


def test_provider_factory_selects_fake_without_credentials(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    provider = create_provider()

    assert isinstance(provider, FakeProvider)
    result = asyncio.run(provider.generate((), ()))
    assert "FakeProvider" in result.text


def test_openai_selection_requires_api_key_only_when_selected(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        create_provider()


def test_provider_factory_selects_openai_without_network_access(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    assert isinstance(create_provider(), OpenAIProvider)


def test_ai_chat_endpoint_uses_harness() -> None:
    application = create_app(
        Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")
    )
    harness = Mock(spec=AIHarness)

    async def chat(message: str):
        return {
            "assistant_text": "One teacher is available.",
            "tool_calls": [],
            "metadata": {},
        }

    harness.chat = chat
    application.dependency_overrides[get_ai_harness] = lambda: harness

    with TestClient(application) as client:
        response = client.post("/ai/chat", json={"message": "Show teachers"})

    assert response.status_code == 200
    assert response.json()["assistant_text"] == "One teacher is available."


def test_ai_chat_reports_missing_provider_configuration(monkeypatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    application = create_app(
        Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")
    )

    with TestClient(application) as client:
        response = client.post("/ai/chat", json={"message": "Show teachers"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "AI_PROVIDER_NOT_CONFIGURED"


def test_ai_chat_runs_with_fake_provider_and_no_credentials(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    application = create_app(
        Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")
    )

    with TestClient(application) as client:
        response = client.post("/ai/chat", json={"message": "Safe local smoke test"})

    assert response.status_code == 200
    assert response.json() == {
        "assistant_text": (
            "FakeProvider is configured; no tool response was scripted."
        ),
        "tool_calls": [],
        "metadata": {
            "provider": "fake",
            "tool_iterations": 0,
            "draft_created": False,
        },
    }
