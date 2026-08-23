"""Centralized environment-backed application configuration."""

import math
import os
from dataclasses import dataclass, field

from school_ai.database.session import get_database_url

_LOCAL_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)


@dataclass(frozen=True)
class Settings:
    app_name: str = "School AI API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = field(default_factory=get_database_url)
    allowed_cors_origins: tuple[str, ...] = _LOCAL_CORS_ORIGINS
    max_solve_seconds: float = 15.0

    @classmethod
    def from_environment(cls) -> "Settings":
        environment = os.getenv("APP_ENV", "development")
        raw_origins = os.getenv("ALLOWED_CORS_ORIGINS")
        origins = (
            tuple(item.strip() for item in raw_origins.split(",") if item.strip())
            if raw_origins is not None
            else _LOCAL_CORS_ORIGINS
            if environment in {"development", "local", "test"}
            else ()
        )
        return cls(
            app_name=os.getenv("APP_NAME", "School AI API"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            environment=environment,
            database_url=get_database_url(),
            allowed_cors_origins=origins,
            max_solve_seconds=_positive_float("MAX_SOLVE_SECONDS", 15.0),
        )


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive finite number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value
