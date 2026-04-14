.PHONY: help init eject install hooks lint format typecheck test check clean

PYTHON ?= python3

help:
	@echo "Targets:"
	@echo "  init       Interactively customize the boilerplate (name, email, etc.)"
	@echo "  eject      Remove boilerplate-only machinery (this script, init target)"
	@echo "  install    Install the package in editable mode with dev extras"
	@echo "  hooks      Install pre-commit and pre-push git hooks"
	@echo "  lint       Run ruff lint and format checks"
	@echo "  format     Auto-fix lint issues and format the code"
	@echo "  typecheck  Run mypy"
	@echo "  test       Run pytest with coverage"
	@echo "  check      Run lint, typecheck, and test (what CI runs)"
	@echo "  clean      Remove build artifacts and caches"

init:
	$(PYTHON) scripts/init_boilerplate.py $(ARGS)

eject:
	$(PYTHON) scripts/eject.py $(ARGS)

install:
	$(PYTHON) -m pip install -e ".[dev]"

hooks:
	pre-commit install

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy

test:
	pytest

check: lint typecheck test

clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf .coverage coverage.xml htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
