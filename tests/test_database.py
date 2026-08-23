from sqlalchemy import text

from school_ai.database.session import (
    create_database_engine,
    get_database_url,
    normalize_database_url,
)


def test_database_url_comes_from_environment(monkeypatch) -> None:
    url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", url)

    assert get_database_url() == url


def test_sqlite_engine_can_be_created_for_tests() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1

    engine.dispose()


def test_railway_postgresql_url_uses_installed_psycopg_driver() -> None:
    assert normalize_database_url("postgresql://user:secret@host/db") == (
        "postgresql+psycopg://user:secret@host/db"
    )
    assert normalize_database_url("postgres://user:secret@host/db") == (
        "postgresql+psycopg://user:secret@host/db"
    )


def test_explicit_driver_url_is_preserved() -> None:
    url = "postgresql+psycopg://user:secret@host/db"
    assert normalize_database_url(url) == url
