"""Explicitly ingest synthetic Markdown policies into the migrated database."""
import argparse
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from school_ai.database.session import create_database_engine, get_database_url
from school_ai.services.policies import PolicyService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("demo_data/policies"))
    args = parser.parse_args()
    engine = create_database_engine(get_database_url())
    try:
        results = PolicyService(sessionmaker(engine)).ingest_directory(args.directory)
        for result in results:
            print(f"{'Ingested' if result['changed'] else 'Kept'} {result['source']}: {result['chunks']} chunks, version {result['version'][:12]}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
