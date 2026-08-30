"""FastAPI application factory and default ASGI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from school_ai.api.errors import register_error_handlers
from school_ai.api.routes import ai, health, schedules, school_data
from school_ai.config import Settings
from school_ai.database.session import create_database_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    database_engine = create_database_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        database_engine.dispose()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="School activity and versioned timetable management API.",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.session_factory = sessionmaker(
        bind=database_engine, autoflush=False, expire_on_commit=False
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(school_data.router)
    application.include_router(schedules.router)
    application.include_router(ai.router)
    register_error_handlers(application)
    return application


app = create_app()
