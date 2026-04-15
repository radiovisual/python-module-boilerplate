"""Interactive initializer for the python-module-boilerplate template.

Run via `make init` (or `python scripts/init_boilerplate.py`). This script
asks a few questions, search-and-replaces the placeholder strings across the
repo.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# DEFAULTS: the real strings baked into the boilerplate that get replaced.    #
#                                                                             #
# Design note: this boilerplate intentionally ships with the maintainer's     #
# real name, email, description, and GitHub handle as working defaults, so    #
# `pip install -e .`, `pytest`, CI workflows, and the README badge all work   #
# in the template state. Using verbose <TOKEN> placeholders would break       #
# hatchling's email validation, PyPI's name validation, and the rendered      #
# CI badge on the boilerplate repo itself.                                    #
#                                                                             #
# The init script treats these literal strings as tokens to find and          #
# replace. When the maintainer runs this, detected defaults (from git         #
# config, cwd) will usually match what's already in the files, so             #
# replacements become no-ops.                                                 #
# --------------------------------------------------------------------------- #

# Keys = literal strings currently in the repo.
# Values = Config attribute names that hold the replacement.
#
# ORDER MATTERS: replacements run top-to-bottom, so longer/more specific
# strings must come before any string that is a substring of them.
# For example, "https://github.com/radiovisual" must be processed before
# "radiovisual" alone, or the URL would be corrupted halfway through.
DEFAULTS: dict[str, str] = {
    "python_module_boilerplate": "module_name",
    "python-module-boilerplate": "project_slug",
    "https://github.com/radiovisual": "author_url",
    "My nifty module boilerplate": "description",
    "Michael Wuergler": "author_name",
    "wuergler@gmail.com": "author_email",
    "radiovisual": "gh_user",
}

# The "scripts" entry is intentional: init_boilerplate.py contains the
# DEFAULTS strings as search targets, so without this skip it would
# rewrite itself mid-run.
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    "scripts",
}

# "" matches extensionless files like LICENSE and .gitignore.
TEXT_SUFFIXES = {
    ".py",
    ".toml",
    ".md",
    ".yml",
    ".yaml",
    ".cfg",
    ".ini",
    ".txt",
    ".editorconfig",
    ".gitignore",
    "",
}


# --------------------------------------------------------------------------- #
# Data types                                                                  #
# --------------------------------------------------------------------------- #


@dataclass
class Config:
    """User's answers. Every attribute name here must also appear as a value
    in the DEFAULTS dict above, otherwise apply_replacements() will KeyError.
    """

    project_slug: str
    module_name: str
    description: str
    author_name: str
    author_email: str
    author_url: str
    gh_user: str
    reset_git: bool


# --------------------------------------------------------------------------- #
# 1. CLI                                                                      #
# --------------------------------------------------------------------------- #


def parse_args() -> argparse.Namespace:
    """Parse command-line flags."""

    parser = argparse.ArgumentParser(
        description="Interactive initilizer for python-module-boilerplate"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="only report the changes, no files will be modified"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="accept all defaults without prompting"
    )

    return parser.parse_args()


# --------------------------------------------------------------------------- #
# 2. Defaults                                                                 #
# --------------------------------------------------------------------------- #


def detect_defaults() -> dict[str, str]:
    """Guess sensible defaults from the environment.

    Strategy:
      project_slug  -> REPO_ROOT.name
      module_name   -> project_slug.replace("-", "_")
      author_name   -> `git config user.name`
      author_email  -> `git config user.email`
      gh_user       -> parse `git config remote.origin.url`
      author_url    -> f"https://github.com/{gh_user}" if gh_user else ""
      description   -> "" (user types their own)
    """

    defaults = {}

    defaults["project_slug"] = REPO_ROOT.name
    defaults["author_name"] = _git_config("user.name") or ""
    defaults["author_email"] = _git_config("user.email") or ""
    defaults["module_name"] = REPO_ROOT.name.replace("-", "_")
    defaults["gh_user"] = ""
    defaults["author_url"] = ""
    defaults["description"] = "My useful module"

    gh_remote_url = _git_config("remote.origin.url")

    if gh_remote_url is not None:
        match = re.search(r"github\.com[:/]([^/]+)/", gh_remote_url)

        username = match.group(1) if match else None

        if username:
            defaults["gh_user"] = username
            defaults["author_url"] = f"https://github.com/{username}"

    return defaults


def _git_config(key: str) -> str | None:
    """Return a git config value or None if unset/git missing."""

    result = subprocess.run(
        ["git", "config", key],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return None

    return result.stdout.strip() or None


# --------------------------------------------------------------------------- #
# 3. Prompts                                                                  #
# --------------------------------------------------------------------------- #


def prompt_user(defaults: dict[str, str], accept_all: bool) -> Config:
    """Ask the user for each field; return a populated Config."""

    config = Config(
        project_slug=defaults["project_slug"],
        author_name=defaults["author_name"],
        author_email=defaults["author_email"],
        module_name=defaults["module_name"],
        gh_user=defaults["gh_user"],
        author_url=defaults["author_url"],
        description=defaults["description"],
        reset_git=False,
    )

    if accept_all:
        return config

    user_project_slug = _ask("What is your module name?", defaults["project_slug"])

    if user_project_slug != defaults["project_slug"]:
        config.module_name = user_project_slug.replace("-", "_")
        config.project_slug = user_project_slug

    user_author_name = _ask("What is your real name on GitHub?", defaults["author_name"])

    if user_author_name != defaults["author_name"]:
        config.author_name = user_author_name

    user_author_username = _ask("What is your username on GitHub?", defaults["gh_user"])

    if user_author_username != defaults["gh_user"]:
        config.gh_user = user_author_username
        config.author_url = f"https://github.com/{user_author_username}"

    user_author_email = _ask("What is your GitHub email address?", defaults["author_email"])

    if user_author_email != defaults["author_email"]:
        config.author_email = user_author_email

    user_description = _ask("What is the project description?", "")

    config.description = user_description

    user_reset_git = _ask("Do you want to erase the .git history? (y/yes/no/n)", "no")

    if user_reset_git.startswith("y"):
        config.reset_git = True

    return config


def _ask(question: str, default: str) -> str:
    question_with_default = f"{question} (default: {default}): "
    response = input(question_with_default).strip()
    return response if response else default


# --------------------------------------------------------------------------- #
# 4. Replacement                                                              #
# --------------------------------------------------------------------------- #


def iter_text_files(root: Path) -> list[Path]:
    """Return every text file under `root`, skipping SKIP_DIRS.

    Returns a list (not a generator) so callers can len() it for logging.
    """

    results: list[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if any(part in SKIP_DIRS for part in path.parts):
            continue

        # Extension filter is what stops us from trying to read_text() a
        # PNG and crashing on UnicodeDecodeError downstream.
        if path.suffix not in TEXT_SUFFIXES:
            continue

        results.append(path)

    return results


def apply_replacements(config: Config, *, dry_run: bool) -> None:
    """Rewrite every DEFAULTS string in every text file under REPO_ROOT."""

    files = iter_text_files(REPO_ROOT)
    changed_count = 0

    for path in files:
        # A text-ish extension can still hold binary (e.g. UTF-16 .txt);
        # skip quietly rather than crash the whole run.
        try:
            original_text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        new_text = original_text

        # DEFAULTS is walked in insertion order — longer strings first so
        # substrings don't corrupt their longer containers.
        for old, attr in DEFAULTS.items():
            replacement = getattr(config, attr)

            # Fast path for the maintainer case: when the user's answer
            # equals the existing string, skip the replace entirely.
            if old == replacement:
                continue

            new_text = new_text.replace(old, replacement)

        if new_text == original_text:
            continue

        rel = path.relative_to(REPO_ROOT)

        if dry_run:
            print(f"would update {rel}")
        else:
            path.write_text(new_text, encoding="utf-8")
            print(f"updated {rel}")

        changed_count += 1

    verb = "would update" if dry_run else "updated"
    print(f"\n{verb} {changed_count} file(s) out of {len(files)} scanned.")


# --------------------------------------------------------------------------- #
# 5. Rename the module directory                                              #
# --------------------------------------------------------------------------- #


def rename_module_dir(config: Config, *, dry_run: bool) -> None:
    """Rename src/python_module_boilerplate/ to src/<new module>/."""
    src = REPO_ROOT / "src" / "python_module_boilerplate"
    dst = REPO_ROOT / "src" / config.module_name

    if src == dst:
        return

    if not src.exists():
        return

    if dry_run:
        print(f"would rename dir: {src.relative_to(REPO_ROOT)} => {dst.relative_to(REPO_ROOT)}")
    else:
        shutil.move(src, dst)
        print(f"renamed dir: {src.relative_to(REPO_ROOT)} => {dst.relative_to(REPO_ROOT)}")


# --------------------------------------------------------------------------- #
# 6. Optional: reset git history                                              #
# --------------------------------------------------------------------------- #


def reset_git_history(*, dry_run: bool) -> None:
    """Delete .git and run `git init` for a clean slate."""
    git_dir = REPO_ROOT / ".git"

    print("WARNING: this will wipe the existing git history.")

    if dry_run:
        if git_dir.exists():
            print(f"would delete {git_dir.relative_to(REPO_ROOT)}")
        print("would run: git init")
        return

    if git_dir.exists():
        shutil.rmtree(git_dir)
        print(f"deleted {git_dir.relative_to(REPO_ROOT)}")

    subprocess.run(["git", "init"], cwd=REPO_ROOT, check=True)
    print("ran: git init")


# --------------------------------------------------------------------------- #
# 7. Final checklist                                                          #
# --------------------------------------------------------------------------- #


def print_checklist(config: Config) -> None:
    """Print a friendly reminder of manual steps the script did NOT do."""

    checklist = textwrap.dedent(f"""
        ------------------------------------------------------------
        Next steps — things the init script did NOT do for you
        ------------------------------------------------------------

        1. Sample code
           src/{config.module_name}/__init__.py still contains the sample
           `unicorn()` function, and tests/ has the matching test. Rewrite
           or delete them before you start building your real module.

        2. GitHub repo
           The README CI badge now points to:
             {config.author_url}/{config.project_slug}
           Make sure that repo actually exists on GitHub (or update the URL).

        3. PyPI trusted publisher
           Before your first release, follow the "Publishing to PyPI" section
           in the README to set up the trusted publisher on PyPI and the
           `pypi` environment on GitHub. No API tokens needed.

        4. Run the test suite
           $ make check
           Confirms lint, typecheck, and tests all pass after the rename.
    """).rstrip()

    if config.reset_git:
        git_step = textwrap.dedent("""
            5. Fresh git history
               Git was reset for you. Make an initial commit when you're ready:
                 $ git add -A && git commit -m "initial commit"
        """).rstrip()
    else:
        git_step = textwrap.dedent("""
            5. Commit the changes
               The init script modified files in place but did NOT commit them.
               Review with `git diff`, then:
                 $ git add -A && git commit -m "init boilerplate"
        """).rstrip()

    eject_step = textwrap.dedent("""
        6. Eject the boilerplate scaffolding
           Once you've verified everything looks right, remove this script
           and the eject script from the repo:
             $ make eject
           This is a one-way operation — do it LAST.
    """).rstrip()

    print(checklist)
    print(git_step)
    print(eject_step)
    print()


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def main() -> int:
    args = parse_args()
    defaults = detect_defaults()
    config = prompt_user(defaults, args.yes)

    apply_replacements(config, dry_run=args.dry_run)
    rename_module_dir(config, dry_run=args.dry_run)

    if config.reset_git:
        reset_git_history(dry_run=args.dry_run)

    print_checklist(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
