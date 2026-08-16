"""PostgreSQL loader: push scan output into the reference warehouse schema.

SQLite stays the zero-setup default; this loader is the graduation path to a
shared database. The SQL is built as a pure function (unit-testable without a
server) and executed with ``psycopg`` (optional dependency,
``pip install .[pg]``). The statement uses ``ON CONFLICT`` so the load is
idempotent: re-running the same CSV converges to the same table state.

The CI pipeline runs this loader for real against a PostgreSQL service
container -- see ``.github/workflows/ci.yml`` (job ``postgres-integration``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .errors import ConfigError, MissingDependencyError
from .models import Business
from .storage import CSV_COLUMNS

TABLE = "businesses"


def build_insert_statement() -> str:
    """Return the idempotent ``INSERT ... ON CONFLICT DO UPDATE`` statement."""
    columns = list(CSV_COLUMNS)
    placeholders = ", ".join(f"%({column})s" for column in columns)
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in columns
        if column not in ("source", "source_id")
    )
    return (
        f"INSERT INTO {TABLE} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        "ON CONFLICT (source, source_id) DO UPDATE SET "
        f"{updates}, scanned_at = now()"
    )


def rows_from_businesses(businesses: Iterable[Business]) -> list[dict[str, Any]]:
    """Map businesses onto parameter dicts matching the insert statement."""
    rows: list[dict[str, Any]] = []
    for business in businesses:
        row = business.to_row()
        rows.append(
            {
                column: bool(row.get(column))
                if column in ("has_website", "has_social")
                else row.get(column)
                for column in CSV_COLUMNS
            }
        )
    return rows


def load_postgres(businesses: Iterable[Business], dsn: str) -> int:
    """Load businesses into PostgreSQL. Returns the number of rows sent.

    Raises:
        MissingDependencyError: if psycopg is not installed.
        ConfigError: if the DSN is empty.
    """
    if not dsn or not dsn.strip():
        raise ConfigError(
            "PostgreSQL DSN is empty. Pass --dsn or set LMS_PG_DSN, e.g. "
            "postgresql://lms:lms@localhost:5432/lms"
        )
    try:
        import psycopg  # noqa: PLC0415 - optional dependency, import on use
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise MissingDependencyError(
            "PostgreSQL loading requires psycopg. "
            "Install it with: pip install 'local-market-scanner[pg]' "
            "or: pip install 'psycopg[binary]'"
        ) from exc

    rows = rows_from_businesses(businesses)
    statement = build_insert_statement()
    with psycopg.connect(dsn) as conn:  # pragma: no cover - needs a server
        with conn.cursor() as cursor:
            cursor.executemany(statement, rows)
        conn.commit()
    return len(rows)
