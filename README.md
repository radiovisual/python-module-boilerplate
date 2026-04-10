# python-module-boilerplate

[![CI](https://github.com/radiovisual/python-module-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/radiovisual/python-module-boilerplate/actions/workflows/ci.yml)

> My nifty Python module

A minimal template for kickstarting a Python package. Opinionated defaults for
`src/` layout, `pyproject.toml`, `ruff` linting, `pytest` testing, pre-commit
hooks, and PyPI publishing via GitHub Actions.

## Install

```sh
pip install python-module-boilerplate
```

## Usage

```python
from python_module_boilerplate import unicorn

unicorn("bob")
#=> 'unicorn & rainbow & bob'
```

## API

### unicorn(string)

Return the input string prefixed with `unicorn & rainbow &`.

#### string

Type: `str`

The string to decorate.

---

## Development

Work inside an isolated environment so the module's dependencies never leak
into your system Python. The stdlib `venv` is the zero-install default; if you
prefer something faster, [`uv`](https://docs.astral.sh/uv/) is a drop-in
alternative (`uv venv && uv pip install -e ".[dev]"`).

```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
make install
```

A `Makefile` wraps the common commands so you don't have to remember each tool's
flags — run `make help` to see every target. Each section below shows the
`make` shortcut alongside the raw command it runs, in case you prefer to invoke
the tools directly.

### Install the git hooks

This uses the [`pre-commit`](https://pre-commit.com/) framework to wire up both
`pre-commit` (lint) and `pre-push` (tests) hooks:

```sh
make hooks
# same as:
pre-commit install
```

Now `ruff` will run before every commit and `pytest` will run before every push.

### Lint

```sh
make lint
# same as:
ruff check .
ruff format --check .
```

To auto-fix:

```sh
make format
# same as:
ruff check --fix .
ruff format .
```

### Type check

```sh
make typecheck
# same as:
mypy
```

### Test

```sh
make test
# same as:
pytest
```

Tests run with coverage enabled by default; a terminal report is printed after
every run.

### Run everything CI runs

```sh
make check
# same as:
ruff check . && ruff format --check . && mypy && pytest
```

### Run all pre-commit hooks manually

```sh
pre-commit run --all-files
pre-commit run --all-files --hook-stage pre-push
```

## Publishing to PyPI

This template ships with a GitHub Actions workflow (`.github/workflows/publish.yml`)
that builds and publishes the package to [PyPI](https://pypi.org/) whenever you
publish a GitHub release. It uses [trusted publishing (OIDC)](https://docs.pypi.org/trusted-publishers/), so no API tokens are needed.

### One-time setup

1. Create the project on PyPI (or reserve the name via a first manual upload).
2. On PyPI, go to **Your projects → Manage → Publishing** and add a trusted
   publisher for this GitHub repo with workflow `publish.yml` and environment `pypi`.
3. In your GitHub repo, create a **pypi** environment under
   **Settings → Environments**.

### Creating a release

1. Bump `version` in `pyproject.toml`.
2. Commit and tag: `git tag v0.1.0 && git push --tags`.
3. On GitHub, create a release from the tag — the workflow will build and publish.

### Manual publish (fallback)

```sh
pip install build twine
python -m build
twine upload dist/*
```

## License

MIT © [Your Name](https://example.com)
