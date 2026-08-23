"""SQLAlchemy engine and session factory configuration."""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    """Return the configured database URL, defaulting to local PostgreSQL."""
    return normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/school_ai",
        )
    )


def normalize_database_url(database_url: str) -> str:
    """Use psycopg for Railway-style PostgreSQL URLs without changing secrets."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create an engine for the supplied URL or the environment configuration."""
    url = normalize_database_url(database_url) if database_url else get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
