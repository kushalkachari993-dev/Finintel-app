import os
import shutil
from pathlib import Path

import pytest


TEST_RUNTIME_DIR = Path(__file__).parent / ".runtime"
TEST_DATABASE_PATH = TEST_RUNTIME_DIR / "finintel-tests.sqlite3"

os.environ["DATABASE_URL"] = (
    f"sqlite:///{TEST_DATABASE_PATH.resolve().as_posix()}"
)
os.environ["AUDIT_DATABASE_PATH"] = str(TEST_DATABASE_PATH.resolve())
os.environ["SENTRY_DSN"] = ""


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database():
    from backend.storage import MigrationRunner

    MigrationRunner(
        database_path=str(TEST_DATABASE_PATH.resolve())
    ).apply_pending()
    yield
    shutil.rmtree(TEST_RUNTIME_DIR, ignore_errors=True)
