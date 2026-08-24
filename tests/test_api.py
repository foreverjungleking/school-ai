from collections.abc import Generator
from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from school_ai.api.app import create_app
from school_ai.api.dependencies import (
    get_school_data_service,
    get_scheduling_service,
    get_session,
)
from school_ai.config import Settings
from school_ai.database.base import Base
from school_ai.database.models import (
    Activity,
    Room,
    RoomAvailability,
    StudentGroup,
    Teacher,
    TeacherAvailability,
)
from school_ai.repositories import ScheduleRepository, SchedulingDataRepository
from school_ai.services import SchedulingService
from school_ai.solver import SchedulingProblem, SolveStatus, SolverResult


@pytest.fixture
def api_context() -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    teacher = Teacher(name="Ms Lim")
    group = StudentGroup(name="Class 7A", size=24)
    room = Room(name="Room 101", capacity=30, room_type="classroom")
    activity = Activity(
        name="Mathematics",
        teacher=teacher,
        student_group=group,
        sessions_per_week=1,
        duration_minutes=60,
        required_room_type="classroom",
    )
    teacher.availability.append(
        TeacherAvailability(
            weekday=0,
            start_time=time(8),
            end_time=time(12),
            available=True,
        )
    )
    room.availability.append(
        RoomAvailability(
            weekday=0,
            start_time=time(8),
            end_time=time(12),
            available=True,
        )
    )
    session.add_all([room, activity])
    session.commit()

    application = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            allowed_cors_origins=("http://localhost:5173",),
        )
    )

    def override_session() -> Generator[Session, None, None]:
        yield session

    application.dependency_overrides[get_session] = override_session
    with TestClient(application) as client:
        yield client, session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _draft_payload() -> dict[str, object]:
    return {
        "time_slots": [
            {
                "id": 1,
                "weekday": 0,
                "start_time": "08:00:00",
                "end_time": "09:00:00",
            },
            {
                "id": 2,
                "weekday": 0,
                "start_time": "09:00:00",
                "end_time": "10:00:00",
            },
        ],
        "max_solve_seconds": 2,
    }


def _create_schedule(client: TestClient, name: str = "2026 timetable") -> int:
    response = client.post("/schedules", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_health_and_openapi(api_context: tuple[TestClient, Session]) -> None:
    client, _ = api_context

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "test",
        "version": "0.1.0",
    }
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "School AI API"


def test_configured_cors_origin_is_allowed(
    api_context: tuple[TestClient, Session],
) -> None:
    client, _ = api_context

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.parametrize(
    ("collection_path", "item_path", "name"),
    (
        ("/teachers", "/teachers/1", "Ms Lim"),
        ("/rooms", "/rooms/1", "Room 101"),
        ("/student-groups", "/student-groups/1", "Class 7A"),
        ("/activities", "/activities/1", "Mathematics"),
    ),
)
def test_school_data_list_and_get_endpoints(
    api_context: tuple[TestClient, Session],
    collection_path: str,
    item_path: str,
    name: str,
) -> None:
    client, _ = api_context

    collection = client.get(collection_path)
    item = client.get(item_path)

    assert collection.status_code == 200
    assert collection.json()[0]["name"] == name
    assert item.status_code == 200
    assert item.json()["name"] == name


@pytest.mark.parametrize(
    "path", ("/teachers/1/availability", "/rooms/1/availability")
)
def test_availability_endpoints(
    api_context: tuple[TestClient, Session], path: str
) -> None:
    client, _ = api_context

    response = client.get(path)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "weekday": 0,
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "available": True,
        }
    ]


def test_complete_schedule_api_workflow(
    api_context: tuple[TestClient, Session],
) -> None:
    client, _ = api_context
    schedule_id = _create_schedule(client)

    first_draft = client.post(
        f"/schedules/{schedule_id}/drafts", json=_draft_payload()
    )
    assert first_draft.status_code == 201
    first_body = first_draft.json()
    first_version_id = first_body["version"]["id"]
    assert first_body["solver_status"] == "OPTIMAL"
    assert first_body["version"]["status"] == "DRAFT"
    assert len(first_body["version"]["lessons"]) == 1

    loaded = client.get(
        f"/schedules/{schedule_id}/versions/{first_version_id}"
    )
    versions = client.get(f"/schedules/{schedule_id}/versions")
    assert loaded.status_code == 200
    assert loaded.json()["lessons"] == first_body["version"]["lessons"]
    assert versions.status_code == 200
    assert [item["version_number"] for item in versions.json()] == [1]

    published = client.post(
        f"/schedules/{schedule_id}/versions/{first_version_id}/publish"
    )
    current = client.get(f"/schedules/{schedule_id}/published")
    schedule = client.get(f"/schedules/{schedule_id}")
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"
    assert published.json()["published_at"] is not None
    assert current.status_code == 200
    assert current.json()["id"] == first_version_id
    assert schedule.json()["published_version_id"] == first_version_id

    second_draft = client.post(
        f"/schedules/{schedule_id}/drafts", json=_draft_payload()
    )
    assert second_draft.status_code == 201
    second_version_id = second_draft.json()["version"]["id"]
    comparison = client.get(
        f"/schedules/{schedule_id}/compare",
        params={
            "from_version_id": first_version_id,
            "to_version_id": second_version_id,
        },
    )
    assert comparison.status_code == 200
    assert comparison.json()["from_version_id"] == first_version_id
    assert comparison.json()["to_version_id"] == second_version_id
    assert set(comparison.json()) == {
        "from_version_id",
        "to_version_id",
        "unchanged",
        "added",
        "removed",
        "changed",
    }


@pytest.mark.parametrize(
    "path",
    (
        "/teachers/999",
        "/rooms/999",
        "/student-groups/999",
        "/activities/999",
        "/schedules/999",
    ),
)
def test_nonexistent_resources_return_404(
    api_context: tuple[TestClient, Session], path: str
) -> None:
    client, _ = api_context

    response = client.get(path)

    assert response.status_code == 404
    assert response.json()["detail"]["code"].endswith("NOT_FOUND")


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    (
        ("get", "/teachers/0", None),
        ("post", "/schedules", {"name": "   "}),
        (
            "post",
            "/schedules/1/drafts",
            {
                "time_slots": [
                    {
                        "id": 1,
                        "weekday": 0,
                        "start_time": "09:00:00",
                        "end_time": "08:00:00",
                    }
                ]
            },
        ),
    ),
)
def test_invalid_requests_return_validation_errors(
    api_context: tuple[TestClient, Session],
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    client, _ = api_context

    response = client.request(method, path, json=json_body)

    assert response.status_code == 422


def test_empty_scheduling_data_returns_specific_safe_error(
    api_context: tuple[TestClient, Session],
) -> None:
    client, session = api_context
    schedule_id = _create_schedule(client, "Empty data timetable")
    for model in (Activity, Teacher, Room, StudentGroup):
        session.query(model).delete()
    session.commit()

    response = client.post(f"/schedules/{schedule_id}/drafts", json=_draft_payload())

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "SCHEDULING_DATA_INCOMPLETE",
            "message": (
                "Cannot generate a schedule until demo data is loaded. "
                "Missing: teachers, rooms, student groups, activities."
            ),
        }
    }


def test_infeasible_generation_has_structured_conflict_response(
    api_context: tuple[TestClient, Session],
) -> None:
    client, _ = api_context
    schedule_id = _create_schedule(client, "Infeasible timetable")
    payload = {
        "time_slots": [
            {
                "id": 1,
                "weekday": 0,
                "start_time": "08:00:00",
                "end_time": "08:30:00",
            }
        ]
    }

    response = client.post(f"/schedules/{schedule_id}/drafts", json=payload)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "SCHEDULE_INFEASIBLE"
    assert detail["solver_status"] == "INFEASIBLE"
    assert client.get(f"/schedules/{schedule_id}/versions").json() == []


def test_unknown_solver_status_has_structured_unavailable_response(
    api_context: tuple[TestClient, Session],
) -> None:
    client, session = api_context

    def unknown_solver(problem: SchedulingProblem) -> SolverResult:
        return SolverResult(
            status=SolveStatus.UNKNOWN,
            solve_duration_seconds=0.05,
            metadata={"solver_status": "UNKNOWN"},
        )

    def override_service() -> SchedulingService:
        return SchedulingService(
            ScheduleRepository(session),
            SchedulingDataRepository(session),
            solver=unknown_solver,
        )

    client.app.dependency_overrides[get_scheduling_service] = override_service
    schedule_id = _create_schedule(client, "Unknown timetable")

    response = client.post(
        f"/schedules/{schedule_id}/drafts", json=_draft_payload()
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SOLVER_STATUS_UNKNOWN"


def test_nested_version_must_belong_to_schedule(
    api_context: tuple[TestClient, Session],
) -> None:
    client, _ = api_context
    first_schedule = _create_schedule(client, "First")
    second_schedule = _create_schedule(client, "Second")
    draft = client.post(
        f"/schedules/{first_schedule}/drafts", json=_draft_payload()
    ).json()

    response = client.get(
        f"/schedules/{second_schedule}/versions/{draft['version']['id']}"
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SCHEDULE_VERSION_NOT_FOUND"


def test_production_cors_defaults_to_no_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ALLOWED_CORS_ORIGINS", raising=False)

    settings = Settings.from_environment()

    assert settings.allowed_cors_origins == ()


def test_cors_origins_are_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_CORS_ORIGINS", "https://demo.example, https://admin.example")

    settings = Settings.from_environment()

    assert settings.allowed_cors_origins == (
        "https://demo.example",
        "https://admin.example",
    )


def test_solver_time_limit_is_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_SOLVE_SECONDS", "12.5")

    assert Settings.from_environment().max_solve_seconds == 12.5


@pytest.mark.parametrize("value", ["0", "-1", "nan", "invalid"])
def test_solver_time_limit_must_be_positive_and_finite(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("MAX_SOLVE_SECONDS", value)

    with pytest.raises(ValueError, match="MAX_SOLVE_SECONDS"):
        Settings.from_environment()


def test_unexpected_errors_do_not_leak_internal_details(
    api_context: tuple[TestClient, Session],
) -> None:
    client, _ = api_context

    def broken_service():
        raise RuntimeError("database password should remain private")

    client.app.dependency_overrides[get_school_data_service] = broken_service
    with TestClient(client.app, raise_server_exceptions=False) as safe_client:
        response = safe_client.get("/teachers")

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "internal server error",
        }
    }
    assert "password" not in response.text
