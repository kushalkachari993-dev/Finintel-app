from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse


def resolve_sqlite_path(
    database_url: str,
) -> str:
    parsed = urlparse(
        database_url
    )

    if parsed.scheme not in {
        "sqlite",
        "sqlite3",
    }:
        raise ValueError(
            "Only sqlite:// database URLs are supported by the free local "
            "storage adapter. Use sqlite:///data/finintel.sqlite3 locally, "
            "or add a Postgres adapter before setting a postgres URL."
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
