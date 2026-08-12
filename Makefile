.PHONY: help install dev test coverage lint format doctor scan leads brief clean

PY ?= python
export PYTHONPATH := src

help:
	@echo "make install   - install runtime dependencies"
	@echo "make dev       - install runtime + dev dependencies"
	@echo "make test      - run the test suite (stdlib unittest, no deps)"
	@echo "make coverage  - run tests with coverage and a 80% floor"
	@echo "make lint      - ruff check"
	@echo "make format    - ruff format"
	@echo "make doctor    - diagnose config and Overpass reachability"
	@echo "make scan      - scan Bursa health facilities into data/bursa_health.csv"
	@echo "make leads     - print qualified leads from the scan CSV"
	@echo "make brief     - render the Markdown outreach brief"

install:
	$(PY) -m pip install -r requirements.txt

dev: install
	$(PY) -m pip install ruff coverage pytest

test:
	$(PY) -m unittest discover -s tests -v

coverage:
	$(PY) -m coverage run -m unittest discover -s tests
	$(PY) -m coverage report --fail-under=80

lint:
	$(PY) -m ruff check src tests

format:
	$(PY) -m ruff format src tests

doctor:
	$(PY) -m lms.cli doctor

scan:
	$(PY) -m lms.cli scan --out data/bursa_health.csv --sqlite

leads:
	$(PY) -m lms.cli leads --csv data/bursa_health.csv

brief:
	$(PY) -m lms.cli brief --csv data/bursa_health.csv --out data/outreach_brief.md

clean:
	rm -rf .coverage htmlcov .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
