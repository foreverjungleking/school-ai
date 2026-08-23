from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

import school_ai.database.models  # noqa: F401
from school_ai.database.base import Base
from school_ai.database.session import create_database_engine


def test_initial_migration_builds_current_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite+pysqlite:///{database_path}"

    command.upgrade(config, "head")
    command.check(config)

    # Open through SQLAlchemy after Alembic releases its migration connection.
    engine = create_database_engine(config.attributes["database_url"])
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert tables == {*Base.metadata.tables, "alembic_version"}
