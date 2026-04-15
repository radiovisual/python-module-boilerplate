# ------------------------------------------------------------------------------
# Venv-agnostic Makefile
#
# Every target runs tools via .venv/bin/... directly, so you do NOT need to
# `source .venv/bin/activate` before running `make test`, `make check`, etc.
# The `venv` target bootstraps .venv on first use, so a fresh clone just needs:
#
#     make venv && make install
#
# ...and from then on `make <anything>` uses the project venv automatically.
#
# Note: because make targets don't activate the venv in your parent shell, you
# won't see the `(.venv)` prompt indicator when running make. The tools are
# still using the venv — it's just invisible. If you want the indicator (or an
# interactive python/pytest session), activate manually with:
#
#     source .venv/bin/activate
# ------------------------------------------------------------------------------

.PHONY: help venv init eject install hooks lint format typecheck test check clean

PYTHON ?= python3
VENV    := .venv
VENV_BIN := $(VENV)/bin

# Tools resolved from the venv so targets never depend on shell activation.
VENV_PYTHON := $(VENV_BIN)/python
RUFF        := $(VENV_BIN)/ruff
MYPY        := $(VENV_BIN)/mypy
PYTEST      := $(VENV_BIN)/pytest
PRE_COMMIT  := $(VENV_BIN)/pre-commit

help:
	@echo "Targets:"
	@echo "  venv       Create .venv if it doesn't exist (run this first on a fresh clone)"
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

# Bootstraps .venv on demand. Other targets depend on $(VENV_PYTHON), so the
# venv is auto-created the first time you run make test / make check / etc.
venv: $(VENV_PYTHON)

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip

init:
	$(PYTHON) scripts/init_boilerplate.py $(ARGS)

eject:
	$(PYTHON) scripts/eject.py $(ARGS)

install: $(VENV_PYTHON)
	$(VENV_PYTHON) -m pip install -e ".[dev]"

hooks: $(VENV_PYTHON)
	$(PRE_COMMIT) install

lint: $(VENV_PYTHON)
	$(RUFF) check .
	$(RUFF) format --check .

format: $(VENV_PYTHON)
	$(RUFF) check --fix .
	$(RUFF) format .

typecheck: $(VENV_PYTHON)
	$(MYPY)

test: $(VENV_PYTHON)
	$(PYTEST)

check: lint typecheck test

clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf .coverage coverage.xml htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
