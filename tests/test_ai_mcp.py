import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from school_ai.ai.harness import AIHarness, HarnessError
from school_ai.ai.models import ChatMessage, ProviderTurn, ToolCall, ToolDefinition
from school_ai.ai.providers.fake import FakeProvider
from school_ai.ai.providers.factory import create_provider
from school_ai.ai.providers.base import ProviderConfigurationError, ProviderResponseError
from school_ai.ai.providers.ollama import OllamaProvider
from school_ai.ai.providers.openai import OpenAIProvider
from school_ai.api.app import create_app
from school_ai.api.dependencies import get_ai_harness
from school_ai.config import Settings
from school_ai.database.models import ScheduleVersionStatus
from school_ai.mcp.client import InProcessMCPClient
from school_ai.mcp.server import SchoolMCPServer, create_mcp_sdk_server
from school_ai.services import SchoolDataService, SchedulingService
from school_ai.services.dto import (
    GenerateScheduleResult,
    ScheduleSummary,
    ScheduleVersionView,
)
from school_ai.services.school_data import TeacherView
from school_ai.solver import SolveStatus


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
    scheduling.get_current_demo_schedule.return_value = ScheduleSummary(
        id=7,
        name="Demo timetable",
        latest_draft_version_id=11,
        published_version_id=10,
    )
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
    return {"schedule_id": 7}


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
    result = server.create_schedule_draft(7, 3)

    scheduling.generate_schedule_draft.assert_called_once_with(7, None, 3)
    assert result["version"]["id"] == 11


def test_mcp_current_schedule_calls_application_service() -> None:
    school_data, scheduling = _services()
    server = SchoolMCPServer(school_data, scheduling)

    result = server.get_current_demo_schedule()

    scheduling.get_current_demo_schedule.assert_called_once_with()
    assert result["published_version_id"] == 10


def test_mcp_published_schedule_resolves_omitted_schedule_id() -> None:
    school_data, scheduling = _services()
    server = SchoolMCPServer(school_data, scheduling)

    result = server.get_published_schedule()

    scheduling.get_current_demo_schedule.assert_called_once_with()
    scheduling.get_published_schedule_version.assert_called_once_with(7)
    assert result["id"] == 11


def test_official_mcp_server_exposes_only_approved_tools() -> None:
    school_data, scheduling = _services()
    sdk_server = create_mcp_sdk_server(SchoolMCPServer(school_data, scheduling))

    names = {item.name for item in asyncio.run(sdk_server.list_tools())}

    assert names == {
        "list_teachers",
        "list_rooms",
        "list_student_groups",
        "list_activities",
        "get_current_demo_schedule",
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
    assert [tool.name for tool in provider.calls[0][1]] == ["list_teachers"]


def test_harness_sends_no_tools_for_capability_question() -> None:
    school_data, scheduling = _services()
    provider = FakeProvider(ProviderTurn(text="I can read school data and make drafts."))

    result = asyncio.run(
        AIHarness(provider, _client(school_data, scheduling)).chat(
            "What can you help me with?"
        )
    )

    assert result.assistant_text.startswith("I can read")
    assert provider.calls[0][1] == ()


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


class _OllamaResponse:
    def __init__(self, message: dict[str, Any]) -> None:
        self._message = message

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return {"message": self._message}


class _OllamaClient:
    response: _OllamaResponse

    def __init__(self, **kwargs: Any) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def post(self, *args: Any, **kwargs: Any) -> _OllamaResponse:
        return self.response


def test_ollama_parses_provider_neutral_json_tool_response(monkeypatch) -> None:
    _OllamaClient.response = _OllamaResponse(
        {
            "content": json.dumps(
                {
                    "tool_calls": [
                        {"name": "list_teachers", "arguments": {}}
                    ],
                    "text": "",
                }
            )
        }
    )
    monkeypatch.setattr(
        "school_ai.ai.providers.ollama.httpx.AsyncClient", _OllamaClient
    )

    turn = asyncio.run(
        OllamaProvider("http://localhost:11434", "test-model").generate((), ())
    )

    assert turn.tool_calls == (ToolCall(name="list_teachers"),)


def test_ollama_accepts_plain_summary_after_tool_result(monkeypatch) -> None:
    _OllamaClient.response = _OllamaResponse(
        {"content": "Daniel Tan and Aisha Rahman are available."}
    )
    monkeypatch.setattr(
        "school_ai.ai.providers.ollama.httpx.AsyncClient", _OllamaClient
    )

    turn = asyncio.run(
        OllamaProvider("http://localhost:11434", "test-model").generate(
            (ChatMessage(role="tool", content='{"success": true}'),),
            (
                ToolDefinition(
                    name="list_teachers",
                    description="List teachers.",
                    input_schema={"type": "object", "properties": {}},
                ),
            ),
        )
    )

    assert turn == ProviderTurn(
        text="Daniel Tan and Aisha Rahman are available."
    )


class _OpenAIClient:
    responses: list[httpx.Response]
    requests: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        response.request = httpx.Request("POST", url)
        return response


def _mock_openai(monkeypatch, *responses: httpx.Response) -> None:
    _OpenAIClient.responses = list(responses)
    _OpenAIClient.requests = []
    monkeypatch.setattr(
        "school_ai.ai.providers.openai.httpx.AsyncClient", _OpenAIClient
    )


def test_openai_parses_normal_responses_api_text(monkeypatch) -> None:
    _mock_openai(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "One teacher."}
                        ],
                    }
                ]
            },
        ),
    )

    turn = asyncio.run(OpenAIProvider("test-key", "gpt-5-mini").generate((), ()))

    assert turn == ProviderTurn(text="One teacher.")


def test_openai_parses_responses_api_function_call(monkeypatch) -> None:
    _mock_openai(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "function_call",
                        "name": "list_teachers",
                        "arguments": "{}",
                        "call_id": "call_123",
                    }
                ]
            },
        ),
    )

    turn = asyncio.run(OpenAIProvider("test-key", "gpt-5-mini").generate((), ()))

    assert turn == ProviderTurn(tool_calls=(ToolCall(name="list_teachers"),))


@pytest.mark.parametrize(
    ("status", "public_message"),
    [
        (400, "rejected the request"),
        (401, "authentication failed"),
        (429, "rate limit or quota exceeded"),
    ],
)
def test_openai_logs_safe_api_error_diagnostics(
    monkeypatch, caplog, status: int, public_message: str
) -> None:
    _mock_openai(
        monkeypatch,
        httpx.Response(
            status,
            json={
                "error": {
                    "message": "sensitive provider detail",
                    "type": "invalid_request_error",
                    "code": "invalid_tool_schema",
                    "param": "tools[0].parameters",
                }
            },
        ),
    )

    with pytest.raises(ProviderResponseError, match=public_message):
        asyncio.run(
            OpenAIProvider("secret-test-key", "gpt-5-mini").generate((), ())
        )

    assert f"status={status}" in caplog.text
    assert "error_type=invalid_request_error" in caplog.text
    assert "error_code=invalid_tool_schema" in caplog.text
    assert "error_param=tools[0].parameters" in caplog.text
    assert "secret-test-key" not in caplog.text
    assert "sensitive provider detail" not in caplog.text


def test_openai_rejects_malformed_json_response(monkeypatch) -> None:
    _mock_openai(
        monkeypatch,
        httpx.Response(200, content=b"not-json"),
    )

    with pytest.raises(ProviderResponseError, match="invalid response"):
        asyncio.run(OpenAIProvider("test-key", "gpt-5-mini").generate((), ()))


def test_openai_sends_non_strict_function_tools(monkeypatch) -> None:
    school_data, scheduling = _services()
    definitions = SchoolMCPServer(school_data, scheduling).tool_definitions
    _mock_openai(monkeypatch, httpx.Response(200, json={"output": []}))

    asyncio.run(
        OpenAIProvider("test-key", "gpt-5-mini").generate((), definitions)
    )

    payload = _OpenAIClient.requests[0]["json"]
    assert payload["model"] == "gpt-5-mini"
    assert payload["tool_choice"] == "auto"
    assert payload["parallel_tool_calls"] is False
    assert {tool["name"] for tool in payload["tools"]} == {
        tool.name for tool in definitions
    }
    assert all(tool["strict"] is False for tool in payload["tools"])


def test_openai_two_turn_list_teachers_flow_executes_one_tool(monkeypatch) -> None:
    school_data, scheduling = _services()
    _mock_openai(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "function_call",
                        "name": "list_teachers",
                        "arguments": "{}",
                        "call_id": "call_123",
                    }
                ]
            },
        ),
        httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "The teacher is Ms Lim.",
                            }
                        ],
                    }
                ]
            },
        ),
    )

    result = asyncio.run(
        AIHarness(
            OpenAIProvider("test-key", "gpt-5-mini"),
            _client(school_data, scheduling),
        ).chat("List the teachers.")
    )

    assert result.assistant_text == "The teacher is Ms Lim."
    assert [execution.name for execution in result.tool_calls] == ["list_teachers"]
    school_data.list_teachers.assert_called_once_with()
    assert len(_OpenAIClient.requests) == 2
    first_payload = _OpenAIClient.requests[0]["json"]
    assert [tool["name"] for tool in first_payload["tools"]] == ["list_teachers"]
    assert first_payload["tools"][0]["strict"] is False
    second_input = _OpenAIClient.requests[1]["json"]["input"]
    assert any(
        item["role"] == "user"
        and item["content"].startswith("Tool result: ")
        and '"name": "list_teachers"' in item["content"]
        and '"Ms Lim"' in item["content"]
        for item in second_input
    )


def test_ollama_rejects_malformed_structured_response(monkeypatch) -> None:
    _OllamaClient.response = _OllamaResponse({"content": "not JSON"})
    monkeypatch.setattr(
        "school_ai.ai.providers.ollama.httpx.AsyncClient", _OllamaClient
    )

    with pytest.raises(ProviderResponseError, match="invalid response"):
        asyncio.run(
            OllamaProvider("http://localhost:11434", "test-model").generate((), ())
        )


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
