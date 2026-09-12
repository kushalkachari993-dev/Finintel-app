import argparse
import logging

from backend.config import settings
from backend.storage.migrations import MigrationRunner
from backend.utils.logging_config import configure_logging


logger = logging.getLogger(__name__)


def configured_migration_runner() -> MigrationRunner:
    return MigrationRunner(
        database_url=settings.AUDIT_DATABASE_URL,
        database_path=settings.AUDIT_DATABASE_PATH,
    )


def apply_configured_migrations() -> list[str]:
    runner = configured_migration_runner()
    applied = runner.apply_pending()
    runner.validate_current()
    return applied


def validate_configured_schema():
    return configured_migration_runner().validate_current()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply or validate the FinIntel database schema."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the schema without applying migrations.",
    )
    arguments = parser.parse_args(argv)
    configure_logging()

    if arguments.check:
        status = validate_configured_schema()
        logger.info(
            "database_schema_current versions=%s",
            ",".join(status.applied_versions),
        )
        return 0

    applied = apply_configured_migrations()
    logger.info(
        "database_migrations_complete applied=%s",
        ",".join(applied) if applied else "none",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
