"""Persistence: SQLite by default, CSV export, optional PostgreSQL.

SQLite is the default so the project runs with zero infrastructure setup.
``sql/schema.sql`` contains the equivalent PostgreSQL schema for when you
graduate to a real database.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import closing
from pathlib import Path

from .models import Business

logger = logging.getLogger(__name__)

CSV_COLUMNS: Sequence[str] = (
    "source",
    "source_id",
    "name",
    "category",
    "district",
    "address",
    "phone",
    "email",
    "website",
    "social_url",
    "opening_hours",
    "lat",
    "lon",
    "has_website",
    "has_social",
    "digital_maturity_score",
    "lead_priority",
)

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    source                 TEXT    NOT NULL,
    source_id              TEXT    NOT NULL,
    name                   TEXT    NOT NULL,
    category               TEXT    NOT NULL,
    district               TEXT,
    address                TEXT,
    phone                  TEXT,
    email                  TEXT,
    website                TEXT,
    social_url             TEXT,
    opening_hours          TEXT,
    lat                    REAL,
    lon                    REAL,
    has_website            INTEGER NOT NULL,
    has_social             INTEGER NOT NULL,
    digital_maturity_score INTEGER NOT NULL,
    lead_priority          TEXT    NOT NULL,
    scanned_at             TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_businesses_priority
    ON businesses (lead_priority, digital_maturity_score);
"""


def write_csv(businesses: Iterable[Business], path: Path) -> int:
    """Write businesses to ``path`` as UTF-8 CSV. Returns the row count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for business in businesses:
            row = business.to_row()
            writer.writerow({key: row.get(key) for key in CSV_COLUMNS})
            count += 1
    logger.info("Wrote %d rows to %s", count, path)
    return count


def init_sqlite(db_path: Path) -> None:
    """Create the SQLite database and schema if they do not exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(SQLITE_SCHEMA)
        conn.commit()


def upsert_sqlite(businesses: Iterable[Business], db_path: Path) -> int:
    """Insert or update businesses in SQLite. Returns the row count."""
    db_path = Path(db_path)
    init_sqlite(db_path)
    columns = list(CSV_COLUMNS)
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(
        f"{c}=excluded.{c}" for c in columns if c not in ("source", "source_id")
    )
    statement = (
        f"INSERT INTO businesses ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(source, source_id) DO UPDATE SET {updates}, "
        "scanned_at=datetime('now')"
    )
    count = 0
    with closing(sqlite3.connect(db_path)) as conn:
        for business in businesses:
            row = business.to_row()
            values = [
                int(row[c]) if c in ("has_website", "has_social") else row.get(c)
                for c in columns
            ]
            conn.execute(statement, values)
            count += 1
        conn.commit()
    logger.info("Upserted %d rows into %s", count, db_path)
    return count
