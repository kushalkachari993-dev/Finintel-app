import sqlite3
from dataclasses import dataclass
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path


def list_migrations(
    migrations_dir: Path = MIGRATIONS_DIR
) -> list[Migration]:
    if not migrations_dir.exists():
        return []

    migrations = []

    for path in sorted(
        migrations_dir.glob("*.sql")
    ):
        version = path.name.split(
            "_",
            1
        )[0]

        if not version.isdigit():
            continue

        migrations.append(
            Migration(
                version=version,
                path=path
            )
        )

    return migrations


class MigrationRunner:
    def __init__(
        self,
        database_path: str,
        migrations_dir: Path = MIGRATIONS_DIR
    ):
        self.database_path = database_path
        self.migrations_dir = migrations_dir

    def connect(self):
        Path(self.database_path).parent.mkdir(
            parents=True,
            exist_ok=True
        )
        return sqlite3.connect(
            self.database_path
        )

    @staticmethod
    def ensure_schema_migrations_table(
        connection
    ):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
            """
        )

    @staticmethod
    def applied_versions(
        connection
    ) -> set[str]:
        rows = connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()

        return {
            row[0]
            for row in rows
        }

    @staticmethod
    def execute_migration_sql(
        connection,
        sql: str
    ):
        statements = [
            statement.strip()
            for statement in sql.split(";")
            if statement.strip()
        ]

        for statement in statements:
            try:
                connection.execute(
                    statement
                )
            except sqlite3.OperationalError as error:
                if "duplicate column name" in str(error).lower():
                    continue

                raise

    def apply_pending(self) -> list[str]:
        applied = []

        with self.connect() as connection:
            self.ensure_schema_migrations_table(
                connection
            )
            existing_versions = self.applied_versions(
                connection
            )

            for migration in list_migrations(
                self.migrations_dir
            ):
                if migration.version in existing_versions:
                    continue

                sql = migration.path.read_text(
                    encoding="utf-8"
                )

                self.execute_migration_sql(
                    connection,
                    sql
                )
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version)
                    VALUES (?)
                    """,
                    (
                        migration.version,
                    )
                )
                applied.append(
                    migration.version
                )

        return applied
