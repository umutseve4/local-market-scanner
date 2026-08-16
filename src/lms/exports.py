"""Analytics exports: date-partitioned Parquet on top of the scan output.

Parquet is the de-facto columnar format for analytics engines (DuckDB, Spark,
BigQuery, Athena). Partitioning by ``scan_date=YYYY-MM-DD`` follows the Hive
layout, so downstream engines can prune partitions instead of scanning
everything.

``pyarrow`` is an *optional* dependency (``pip install .[export]``): the core
scanner stays zero-infrastructure, and this module fails with a clear,
actionable error instead of an ImportError traceback.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import MissingDependencyError
from .models import Business
from .storage import CSV_COLUMNS


def _load_pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow  # noqa: PLC0415 - optional dependency, import on use
        import pyarrow.parquet  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise MissingDependencyError(
            "Parquet export requires pyarrow. "
            "Install it with: pip install 'local-market-scanner[export]' "
            "or: pip install pyarrow"
        ) from exc
    return pyarrow, pyarrow.parquet


def partition_dir(out_dir: Path, scan_date: str) -> Path:
    """Return the Hive-style partition directory for one scan date."""
    return Path(out_dir) / f"scan_date={scan_date}"


def export_parquet(
    businesses: Iterable[Business],
    out_dir: Path,
    *,
    scan_date: str | None = None,
) -> tuple[Path, int]:
    """Write businesses to a date-partitioned Parquet file.

    Returns the written file path and the row count.

    Raises:
        MissingDependencyError: if pyarrow is not installed.
        ValueError: if there are no rows to export.
    """
    pa, pq = _load_pyarrow()

    date = scan_date or datetime.now(UTC).strftime("%Y-%m-%d")
    rows = [
        {column: item.to_row().get(column) for column in CSV_COLUMNS}
        for item in businesses
    ]
    if not rows:
        raise ValueError("No rows to export; run a scan first.")

    target_dir = partition_dir(Path(out_dir), date)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "part-0000.parquet"

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, target)
    return target, len(rows)
