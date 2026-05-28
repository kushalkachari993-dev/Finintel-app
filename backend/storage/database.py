from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse


POSTGRES_SCHEMES = {
    "postgres",
    "postgresql"
}

SQLITE_SCHEMES = {
    "sqlite",
    "sqlite3"
}


def database_backend(
    database_url: str
) -> str:

    parsed = urlparse(
        database_url
    )

    if parsed.scheme in SQLITE_SCHEMES:
        return "sqlite"

    if parsed.scheme in POSTGRES_SCHEMES:
        return "postgres"

    raise ValueError(
        f"Unsupported database URL scheme: {parsed.scheme}"
    )


def is_sqlite_url(
    database_url: str
) -> bool:

    return database_backend(
        database_url
    ) == "sqlite"


def normalize_database_url(
    database_url: str
) -> str:

    if database_url.startswith(
        "postgres://"
    ):
        return (
            "postgresql://"
            + database_url.removeprefix(
                "postgres://"
            )
        )

    return database_url


def resolve_sqlite_path(
    database_url: str,
) -> str:
    parsed = urlparse(
        database_url
    )

    if parsed.scheme not in SQLITE_SCHEMES:
        raise ValueError(
            "SQLite database URL must use sqlite:// or sqlite3://."
        )

    if parsed.netloc and parsed.netloc != ".":
        raw_path = f"{parsed.netloc}{parsed.path}"
    else:
        raw_path = parsed.path

    path = unquote(
        raw_path
    )

    if path.startswith("/") and len(path) >= 4 and path[2] == ":":
        path = path[1:]
    elif path.startswith("/"):
        path = path[1:]

    if not path:
        raise ValueError(
            "SQLite database URL must include a file path."
        )

    return str(
        Path(path)
    )
