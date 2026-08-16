# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0]

### Added

- **Scan history** (`history.py`): `lms scan --track` records every run into
  SQLite (`scan_runs` + `business_history`) and diffs it against the previous
  run, classifying each business as `new`, `changed` or `unchanged`.
  `--track` implies `--sqlite`.
- `lms runs` command: lists tracked runs newest-first; `--changes N` prints
  the per-business change log of a single run.
- **Data contract** (`contract.py`): 9 explicit validation rules (required
  fields, unique key, lat range, lon range, score range, priority values,
  URL scheme, `+90` E.164 phone format, e-mail shape). `lms validate` prints a
  PASS/FAIL summary, exits non-zero on failure and can write a JSON or
  Markdown report with `--report`.
- **Parquet export** (`exports.py`): `lms export` writes the scan as
  Parquet partitioned by `scan_date=YYYY-MM-DD/` (Hive-style), ready for
  DuckDB/Spark/Athena-style consumers. Requires the `export` extra
  (`pip install .[export]`).
- **PostgreSQL loader** (`pg_loader.py`): `lms load-pg` bulk-upserts the CSV
  into the `businesses` table via `ON CONFLICT` using `psycopg`. DSN comes
  from `--dsn` or `LMS_PG_DSN`. Requires the `pg` extra.
- `--version` flag on the CLI.
- `MissingDependencyError` for optional dependencies (`pyarrow`, `psycopg`)
  with actionable install hints; maps to exit code `1`.
- `sql/schema.sql`: PostgreSQL mirrors of `scan_runs` and `business_history`
  (JSONB snapshots).
- `docker-compose.yml`: one-command local PostgreSQL 16 with the schema
  applied on first start.
- `.pre-commit-config.yaml`: ruff + hygiene hooks (trailing whitespace,
  merge conflicts, private key detection).
- `docs/ARCHITECTURE.md`: module map, data flow and design decisions.
- CI: smoke tests for all new commands, an advisory `mypy` job and a
  `postgres-integration` job that loads the fixture into a real
  PostgreSQL 16 service and asserts idempotent upserts.
- Test suite grown to **179 tests**, all offline (36 module tests +
  16 CLI tests added).

### Changed

- Package version is now single-sourced from `lms.__version__`
  (`dynamic = ["version"]` in `pyproject.toml`).
- New optional dependency extras: `export` (pyarrow) and `pg` (psycopg).

## [0.2.0]

### Added

- `lms doctor` command: prints the resolved configuration and probes every
  Overpass endpoint, so connectivity problems are diagnosed instead of guessed.
  `--offline` skips all network access.
- `lms brief` command: renders a Turkish Markdown outreach brief
  (`outreach.py`) with a per-lead opening line, missing digital assets and a
  recommended offer.
- Mirror fallback for the Overpass source: `OVERPASS_MIRRORS` plus two built-in
  public mirrors, each with `MAX_RETRIES` attempts.
- Exponential backoff that honours a server-sent `Retry-After` header.
- Typed exception hierarchy in `errors.py` (`ConfigError`, `SourceError`,
  `OverpassUnavailableError`, `OverpassResponseError`).
- Stable process exit codes: `0` success, `1` expected failure, `2` unexpected
  error, `3` data source unreachable.
- Settings validation at construction time and clear errors for malformed
  environment variables.
- Response payload validation before parsing (shape and `elements` type).
- Test suite grown to 127 tests, all offline: retry/mirror/backoff behaviour,
  brief rendering, configuration validation and CLI command coverage.
- `Makefile`, `CONTRIBUTING.md`, `SECURITY.md`, coverage configuration and a
  CLI smoke test in CI across Python 3.11-3.13.

### Changed

- `google_places_api_key` is now `repr=False`, so printing or logging
  `Settings` can never leak the key.
- `DEFAULT_OVERPASS_MIRRORS` no longer duplicates the primary endpoint.
- CSV loading moved out of `cmd_leads` into a reusable `load_csv()`.

## [0.1.0]

### Added

- Initial release: Overpass-based scan of Bursa health facilities, a 0-100
  digital maturity score, lead qualification, CSV and SQLite export, a CLI
  with `scan` and `leads`, and a first test suite.
