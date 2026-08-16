"""Scan-run history: an incremental, idempotent pipeline on top of SQLite.

``storage.upsert_sqlite`` keeps only the *current* state of every business:
re-running a scan overwrites the previous row and the change is lost. This
module adds two tables so every scan becomes an auditable, immutable event:

* ``scan_runs``          -- one row per pipeline execution (run metadata).
* ``business_history``   -- one immutable snapshot per business per run,
                            classified as ``new`` / ``changed`` / ``unchanged``.

Re-running the same input is safe (idempotent): the current-state table ends
up identical and the run is recorded with ``unchanged`` snapshots, so you can
prove nothing moved.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Business
from .storage import CSV_COLUMNS, init_sqlite

HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_runs (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    source          TEXT    NOT NULL,
    bbox            TEXT,
    total_count     INTEGER NOT NULL DEFAULT 0,
    new_count       INTEGER NOT NULL DEFAULT 0,
    changed_count   INTEGER NOT NULL DEFAULT 0,
    unchanged_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS business_history (
    run_id      INTEGER NOT NULL REFERENCES scan_runs(run_id),
    source      TEXT    NOT NULL,
    source_id   TEXT    NOT NULL,
    change_type TEXT    NOT NULL
        CHECK (change_type IN ('new', 'changed', 'unchanged')),
    snapshot    TEXT    NOT NULL,
    recorded_at TEXT    NOT NULL,
    PRIMARY KEY (run_id, source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_history_business
    ON business_history (source, source_id, run_id);
"""

#: Fields whose change flips a snapshot from ``unchanged`` to ``changed``.
TRACKED_FIELDS: tuple[str, ...] = tuple(
    c for c in CSV_COLUMNS if c not in ("source", "source_id")
)


@dataclass(frozen=True)
class ScanRunResult:
    """Summary of one recorded pipeline execution."""

    run_id: int
    total: int
    new: int
    changed: int
    unchanged: int


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_history(db_path: Path) -> None:
    """Create the history tables (and the base schema) if missing."""
    init_sqlite(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(HISTORY_SCHEMA)
        conn.commit()


def _normalise_value(column: str, value: Any) -> Any:
    if column in ("has_website", "has_social"):
        return int(bool(value))
    return value


def _classify(
    conn: sqlite3.Connection, row: dict[str, Any]
) -> str:
    cursor = conn.execute(
        f"SELECT {', '.join(TRACKED_FIELDS)} FROM businesses "
        "WHERE source = ? AND source_id = ?",
        (row["source"], row["source_id"]),
    )
    existing = cursor.fetchone()
    if existing is None:
        return "new"
    for column, old in zip(TRACKED_FIELDS, existing, strict=True):
        if _normalise_value(column, old) != _normalise_value(column, row.get(column)):
            return "changed"
    return "unchanged"


def record_scan_run(
    businesses: Iterable[Business],
    db_path: Path,
    *,
    source: str = "overpass",
    bbox: tuple[float, float, float, float] | None = None,
) -> ScanRunResult:
    """Record one scan as an immutable run and sync the current-state table.

    The whole run is a single transaction: either the run, every snapshot and
    every upsert land together, or nothing does.
    """
    db_path = Path(db_path)
    init_history(db_path)

    columns = list(CSV_COLUMNS)
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(
        f"{c}=excluded.{c}" for c in columns if c not in ("source", "source_id")
    )
    upsert = (
        f"INSERT INTO businesses ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(source, source_id) DO UPDATE SET {updates}, "
        "scanned_at=datetime('now')"
    )

    counts = {"new": 0, "changed": 0, "unchanged": 0}
    started = _utcnow()
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.execute(
            "INSERT INTO scan_runs (started_at, source, bbox) VALUES (?, ?, ?)",
            (started, source, json.dumps(bbox) if bbox else None),
        )
        run_id = int(cursor.lastrowid or 0)

        for business in businesses:
            row = business.to_row()
            change_type = _classify(conn, row)
            counts[change_type] += 1
            conn.execute(
                "INSERT INTO business_history "
                "(run_id, source, source_id, change_type, snapshot, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    row["source"],
                    row["source_id"],
                    change_type,
                    json.dumps(
                        {c: _normalise_value(c, row.get(c)) for c in columns},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    _utcnow(),
                ),
            )
            values = [_normalise_value(c, row.get(c)) for c in columns]
            conn.execute(upsert, values)

        total = sum(counts.values())
        conn.execute(
            "UPDATE scan_runs SET finished_at = ?, total_count = ?, "
            "new_count = ?, changed_count = ?, unchanged_count = ? "
            "WHERE run_id = ?",
            (
                _utcnow(),
                total,
                counts["new"],
                counts["changed"],
                counts["unchanged"],
                run_id,
            ),
        )
        conn.commit()

    return ScanRunResult(
        run_id=run_id,
        total=total,
        new=counts["new"],
        changed=counts["changed"],
        unchanged=counts["unchanged"],
    )


def list_runs(db_path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent scan runs, newest first."""
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT run_id, started_at, finished_at, source, bbox, total_count, "
            "new_count, changed_count, unchanged_count "
            "FROM scan_runs ORDER BY run_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def changes_for_run(db_path: Path, run_id: int) -> list[dict[str, Any]]:
    """Return the ``new``/``changed`` snapshots of one run (audit view)."""
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source, source_id, change_type, snapshot, recorded_at "
            "FROM business_history "
            "WHERE run_id = ? AND change_type != 'unchanged' "
            "ORDER BY change_type, source_id",
            (run_id,),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["snapshot"] = json.loads(item["snapshot"])
        result.append(item)
    return result
