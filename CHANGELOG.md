# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
