# Contributing

## Local setup

```bash
git clone https://github.com/umutseve4/local-market-scanner.git
cd local-market-scanner
python -m venv .venv && source .venv/bin/activate
make dev
cp .env.example .env
```

## Before every commit

```bash
make lint       # ruff check src tests
make test       # 127 tests, all offline
make coverage   # fails below 80%
```

The test suite must not touch the network. Every HTTP interaction is faked
with the `FakeSession` / `FakeResponse` helpers in
`tests/test_overpass_retry.py`. A test that needs the real Overpass API is a
test that will be flaky in CI.

## Definition of done for a change

1. The behaviour is implemented.
2. It has a test that fails without the change.
3. `make lint`, `make test` and `make coverage` pass.
4. Public functions have a docstring stating what they raise.
5. `CHANGELOG.md` has an entry under `Unreleased`.
6. `README.md` is updated if the CLI surface changed.

## Commit messages

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`,
`chore:`. Keep the subject under 72 characters and describe the behaviour
change, not the file list.

## Code style

- Line length 100, enforced by ruff.
- `from __future__ import annotations` at the top of every module.
- Type hints on every public function.
- Errors are raised as the typed exceptions in `src/lms/errors.py`; the CLI is
  the only layer that converts them into exit codes.
- Never add a hardcoded secret, and never disable TLS verification.

## Scope

This project scores the public digital presence of health-sector businesses
and ranks outreach leads. Proposals that add HTML scraping of sources whose
terms forbid it will be rejected.
