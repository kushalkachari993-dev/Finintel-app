import os
from pathlib import Path

from dotenv import load_dotenv

from backend.storage import resolve_sqlite_path
from backend.storage import MigrationRunner

load_dotenv()

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY"
)

APP_ENV = os.getenv(
    "APP_ENV",
    "development"
)

APP_RELEASE = os.getenv(
    "APP_RELEASE",
    "finintel-ai@0.1.0"
)

SENTRY_DSN = os.getenv(
    "SENTRY_DSN",
    ""
)

SENTRY_TRACES_SAMPLE_RATE = float(
    os.getenv(
        "SENTRY_TRACES_SAMPLE_RATE",
        "0.05"
    )
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

GROQ_FAST_MODEL = os.getenv(
    "GROQ_FAST_MODEL",
    "llama-3.1-8b-instant"
)

GROQ_COMPLEX_MODEL = os.getenv(
    "GROQ_COMPLEX_MODEL",
    "llama-3.3-70b-versatile"
)

BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    "http://127.0.0.1:8000"
)

FRONTEND_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ALLOWED_ORIGINS",
        (
            "http://localhost:8501,"
            "http://127.0.0.1:8501,"
            "http://localhost:5173,"
            "http://127.0.0.1:5173,"
            "http://localhost:5174,"
            "http://127.0.0.1:5174,"
            "http://localhost:5175,"
            "http://127.0.0.1:5175"
        )
    ).split(",")
    if origin.strip()
]

APP_API_KEY = os.getenv(
    "APP_API_KEY"
)

API_CLIENTS_JSON = os.getenv(
    "API_CLIENTS_JSON"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///data/finintel.sqlite3"
)


DEFAULT_SQLITE_DATABASE_PATH = resolve_sqlite_path(
    DATABASE_URL
)

AUTH_DATABASE_PATH = os.getenv(
    "AUTH_DATABASE_PATH"
) or DEFAULT_SQLITE_DATABASE_PATH

AUDIT_DATABASE_PATH = os.getenv(
    "AUDIT_DATABASE_PATH"
) or DEFAULT_SQLITE_DATABASE_PATH

AUTH_TOKEN_SECRET = os.getenv(
    "AUTH_TOKEN_SECRET",
    APP_API_KEY
    or "dev-only-change-me"
)

AUTH_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "AUTH_TOKEN_EXPIRE_MINUTES",
        "1440"
    )
)

AUTH_ALLOW_REGISTRATION = (
    os.getenv(
        "AUTH_ALLOW_REGISTRATION",
        "true"
    ).lower()
    == "true"
)

AUTH_EMAIL_VERIFICATION_TOKEN_MINUTES = int(
    os.getenv(
        "AUTH_EMAIL_VERIFICATION_TOKEN_MINUTES",
        "1440"
    )
)

AUTH_PASSWORD_RESET_TOKEN_MINUTES = int(
    os.getenv(
        "AUTH_PASSWORD_RESET_TOKEN_MINUTES",
        "30"
    )
)

AUTH_INITIAL_ADMIN_EMAILS = [
    email.strip().lower()
    for email in os.getenv(
        "AUTH_INITIAL_ADMIN_EMAILS",
        ""
    ).split(",")
    if email.strip()
]

CLERK_JWKS_URL = os.getenv(
    "CLERK_JWKS_URL"
)

CLERK_ISSUER = os.getenv(
    "CLERK_ISSUER"
)

CLERK_AUDIENCE = os.getenv(
    "CLERK_AUDIENCE"
)

RATE_LIMIT_PER_MINUTE = int(
    os.getenv(
        "RATE_LIMIT_PER_MINUTE",
        "30"
    )
)

CHAT_EXECUTION_TIMEOUT_SECONDS = float(
    os.getenv(
        "CHAT_EXECUTION_TIMEOUT_SECONDS",
        "45"
    )
)

EXTERNAL_CALL_TIMEOUT_SECONDS = float(
    os.getenv(
        "EXTERNAL_CALL_TIMEOUT_SECONDS",
        "20"
    )
)

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
)

STOCK_DATA_CACHE_SECONDS = int(
    os.getenv(
        "STOCK_DATA_CACHE_SECONDS",
        "300"
    )
)

SEARCH_CACHE_SECONDS = int(
    os.getenv(
        "SEARCH_CACHE_SECONDS",
        "600"
    )
)

REDIS_URL = os.getenv(
    "REDIS_URL"
)

TICKER_CACHE_SECONDS = int(
    os.getenv(
        "TICKER_CACHE_SECONDS",
        "3600"
    )
)

RAG_ENABLED = (
    os.getenv(
        "RAG_ENABLED",
        "true"
    ).lower()
    == "true"
)

RAG_TOP_K = int(
    os.getenv(
        "RAG_TOP_K",
        "3"
    )
)

RAG_MIN_SCORE = float(
    os.getenv(
        "RAG_MIN_SCORE",
        "0.08"
    )
)

USD_TO_INR_RATE = float(
    os.getenv(
        "USD_TO_INR_RATE",
        "83.0"
    )
)

SYMBOL_MASTER_PATH = os.getenv(
    "SYMBOL_MASTER_PATH",
    "data/market/indian_equities.csv"
)


def validate_required_settings():

    missing = []

    if not GROQ_API_KEY:

        missing.append("GROQ_API_KEY")

    if not TAVILY_API_KEY:

        missing.append("TAVILY_API_KEY")

    if (
        not APP_API_KEY
        and not API_CLIENTS_JSON
        and not AUTH_TOKEN_SECRET
    ):

        missing.append(
            "APP_API_KEY, API_CLIENTS_JSON, or AUTH_TOKEN_SECRET"
        )

    auth_parent = Path(
        AUTH_DATABASE_PATH
    ).parent
    auth_parent.mkdir(
        parents=True,
        exist_ok=True
    )

    audit_parent = Path(
        AUDIT_DATABASE_PATH
    ).parent
    audit_parent.mkdir(
        parents=True,
        exist_ok=True
    )

    for database_path in {
        AUTH_DATABASE_PATH,
        AUDIT_DATABASE_PATH
    }:
        MigrationRunner(
            database_path
        ).apply_pending()

    if missing:

        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
        )
