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

# Repo root = the parent of the `scripts/` directory this file lives in.
# __file__ is the path to this script; .resolve() makes it absolute.
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
# Instead, the init script treats these literal strings as tokens to find     #
# and replace. When the original maintainer uses the boilerplate, the         #
# detected defaults (from git config, cwd) will usually match what's already  #
# in the files, so replacements become no-ops and nothing visibly changes.    #
# Other users will get the expected find/replace behavior.                    #
# --------------------------------------------------------------------------- #

# Keys = literal strings currently in the repo.
# Values = Config attribute names that hold the replacement.
#
# ORDER MATTERS: replacements run top-to-bottom, so longer/more specific
# strings must come before any string that is a substring of them.
# For example, "https://github.com/radiovisual" must be processed before
# "radiovisual" alone, or the URL would be corrupted halfway through.
DEFAULTS: dict[str, str] = {
    # --- Python identifier — src/ dir name, imports, pyproject tooling config.
    #     (Also handled by the directory rename step.)
    "python_module_boilerplate": "module_name",
    # --- PyPI project name — pyproject.toml `name`, README badge URL,
    #     README install command, .github/workflows/publish.yml PyPI URL.
    "python-module-boilerplate": "project_slug",
    # --- Author URL — LICENSE, README footer. Processed BEFORE the bare
    #     "radiovisual" token so the URL is replaced as a whole unit.
    "https://github.com/radiovisual": "author_url",
    # --- Project description — pyproject.toml, README blockquote.
    "My nifty module boilerplate": "description",
    # --- Author name — pyproject.toml authors, LICENSE, README footer.
    "Michael Wuergler": "author_name",
    # --- Author email — pyproject.toml authors, LICENSE.
    "wuergler@gmail.com": "author_email",
    # --- Bare GitHub username — README badge URL, pyproject.toml project.urls.
    #     Must come LAST because it's a substring of the author_url above.
    "radiovisual": "gh_user",
}

# Files that the script is allowed to touch. Anything under .git, .venv,
# caches, etc. is skipped automatically in apply_replacements().
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

# File extensions we treat as text and are willing to rewrite.
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
    """User's answers. One field per DEFAULTS value + a couple of flags.

    NOTE: @dataclass auto-generates __init__, __repr__, __eq__ for you.
    It's the closest thing Python has to a TS `interface` you can instantiate.

    Every attribute name here must appear as a value in the DEFAULTS dict
    above, otherwise apply_replacements() will KeyError on that entry.
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

    Return a dict whose keys match Config attribute names (so prompt_user
    can look them up directly).

    Strategy:
      project_slug  -> REPO_ROOT.name                          (dir name)
      module_name   -> project_slug.replace("-", "_")          (PEP 8 import name)
      author_name   -> `git config --global user.name`
      author_email  -> `git config --global user.email`
      gh_user       -> parse `git config --global remote.origin.url`
                       (e.g. git@github.com:foo/bar.git -> "foo")
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
        # extract the user's github username from an SSH or HTTPS origin URL
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
    """Return a list of every text file under `root`, skipping junk dirs.

    Used by apply_replacements() to figure out which files to scan for
    boilerplate strings. We return a plain list (not a generator) so the
    caller can len() it for logging.
    """

    # Accumulator for the files we want to keep.
    # Building a list and returning it is the simplest approach — no fancy
    # generator/yield stuff needed here.
    results: list[Path] = []

    # Path.rglob("*") walks the tree recursively and yields every path it
    # finds — files AND directories, at every depth. It's the pathlib
    # equivalent of `find . -print` or Node's `fs.readdir` with recursion.
    #
    # The "*" glob pattern matches anything; we filter manually below because
    # our filtering logic (SKIP_DIRS, suffix check) is more than a single
    # glob can express.
    for path in root.rglob("*"):
        # rglob yields directories too — we only want files. is_dir() entries
        # would blow up on read_text() later, so filter them out here.
        if not path.is_file():
            continue

        # Skip anything living inside a junk directory (.git, .venv, caches,
        # node_modules, build artifacts, etc). SKIP_DIRS is defined near the
        # top of this file.
        #
        # path.parts is a tuple of every path component, e.g.
        #   Path("src/.venv/lib/foo.py").parts == ("src", ".venv", "lib", "foo.py")
        #
        # `any(...)` is Python's short-circuit OR over an iterable — it
        # returns True as soon as it finds a matching element. So this
        # reads as: "is ANY component of this path in the skip set?"
        # (TS analog: path.split("/").some(part => SKIP_DIRS.has(part)))
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        # Only keep files whose extension we consider "text". TEXT_SUFFIXES
        # includes "" for extensionless files like LICENSE or .gitignore.
        #
        # path.suffix returns the LAST extension including the dot, e.g.
        #   Path("foo.py").suffix    == ".py"
        #   Path("foo.tar.gz").suffix == ".gz"    (just the last one!)
        #   Path("LICENSE").suffix    == ""
        #
        # This filter is why iter_text_files exists at all: it stops us
        # from trying to read_text() a PNG and crashing on UnicodeDecodeError.
        if path.suffix not in TEXT_SUFFIXES:
            continue

        # Passed every filter — this file is in scope for replacement.
        results.append(path)

    return results


def apply_replacements(config: Config, *, dry_run: bool) -> None:
    """Rewrite every DEFAULTS string in every text file under REPO_ROOT.

    The `*` in the signature makes `dry_run` keyword-only — callers must
    write `apply_replacements(cfg, dry_run=True)`, never positional.
    This is a Python idiom for boolean flags; it prevents the confusing
    `apply_replacements(cfg, True)` call site where you can't tell what
    the True means without jumping to the definition.
    """

    # Collect every text file we're allowed to touch. Building this list
    # once up front (instead of walking the tree on demand) lets us report
    # a total count and gives us a stable set of files to iterate.
    files = iter_text_files(REPO_ROOT)

    # Counter so we can print a nice summary at the end. We only increment
    # for files that actually changed — not every file we looked at.
    changed_count = 0

    # Outer loop: each file gets its own read/replace/write cycle.
    for path in files:
        # Read the file as text. encoding="utf-8" is explicit (Python's
        # default is platform-dependent, which is a recipe for subtle bugs
        # on Windows). Path.read_text() is the pathlib one-liner for
        # "open, read the whole thing, close" — no file handles to manage.
        #
        # try/except guards against the edge case where iter_text_files()
        # let through a file with a text-ish extension that actually contains
        # binary data (rare but possible — e.g. a .txt file that's really
        # UTF-16). We just skip it quietly rather than crashing the whole run.
        try:
            original_text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        # `new_text` starts as a copy of the original. We'll mutate it by
        # repeatedly calling .replace() below. Note that Python strings are
        # IMMUTABLE — every .replace() call returns a NEW string rather than
        # modifying the existing one in place. So this variable gets rebound
        # to a fresh string each iteration. (TS analog: same — strings are
        # immutable there too.)
        new_text = original_text

        # Inner loop: walk the DEFAULTS dict in insertion order. This order
        # matters! DEFAULTS is arranged longest-first so "https://github.com/radiovisual"
        # gets replaced before the bare "radiovisual" — otherwise we'd corrupt
        # URLs mid-replacement. Python dicts preserve insertion order (since 3.7),
        # so we can rely on this ordering just by how the dict literal is written.
        #
        # .items() yields (key, value) pairs. Here:
        #   old  = the literal string we're searching for  (e.g. "Michael Wuergler")
        #   attr = the Config attribute name holding the replacement (e.g. "author_name")
        for old, attr in DEFAULTS.items():
            # getattr(obj, "name") is Python's dynamic attribute lookup —
            # it's equivalent to `obj.name`, but lets you pass the attribute
            # name as a STRING computed at runtime. That's exactly what we
            # need here because `attr` is a variable. Without getattr, we'd
            # have to write a big if/elif chain mapping each DEFAULTS key to
            # a specific Config field. (TS analog: obj[attr] with a keyof-typed
            # string, though TS doesn't need a helper for it.)
            replacement = getattr(config, attr)

            # Fast path: if the user's answer happens to match the existing
            # string, skip the work. This is the common case when the
            # maintainer runs the script — their git config returns the same
            # values that are already in the repo, so most replacements
            # become no-ops. Checking here avoids calling .replace() at all.
            if old == replacement:
                continue

            # str.replace(old, new) scans `new_text` and returns a new string
            # with every occurrence of `old` swapped for `new`. It does NOT
            # mutate the original (strings are immutable — see note above),
            # so we reassign the result back to `new_text`.
            #
            # If `old` doesn't appear in the file, .replace() is a cheap no-op
            # that returns the original string. We don't need to pre-check.
            new_text = new_text.replace(old, replacement)

        # After the inner loop, compare the final text to the original.
        # If they're identical, this file had no replacements and we can
        # skip writing it — this avoids touching mtimes on untouched files
        # (useful for build caches, git status, etc).
        if new_text == original_text:
            continue

        # At least one replacement landed. Time to report and/or write.
        #
        # path.relative_to(REPO_ROOT) strips the long absolute path prefix
        # so log lines are readable — e.g. "src/foo.py" instead of the full
        # "/home/wuerg/gitprojects/python-module-boilerplate/src/foo.py".
        rel = path.relative_to(REPO_ROOT)

        if dry_run:
            # Dry run: report what WOULD change but don't touch the disk.
            # This is how users preview the script's effect safely.
            print(f"would update {rel}")
        else:
            # Real run: write the new content back to the same path.
            # write_text() overwrites the file atomically-ish (it opens,
            # truncates, writes, closes). Same encoding as the read side —
            # always be explicit about encoding when doing text I/O.
            path.write_text(new_text, encoding="utf-8")
            print(f"updated {rel}")

        changed_count += 1

    # Final summary line. Using a ternary-ish f-string expression to tweak
    # the verb based on dry_run — purely cosmetic.
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
    """Delete .git and run `git init` for a clean slate.

    Only called if config.reset_git is True.
    """
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

    # textwrap.dedent removes the common leading whitespace from every line
    # in a multiline string. This lets us write the block indented naturally
    # (matching the surrounding code) instead of awkwardly flush-left against
    # the margin. At print time the indentation collapses to zero.
    #
    # Triple-quoted strings preserve newlines and whitespace verbatim, so
    # what you see in source is what gets printed (minus the shared indent).
    #
    # The leading "\n" gives us a blank line before the header so it doesn't
    # run into the previous command's output.
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

    # The "reset git" branch of the checklist only makes sense depending
    # on what the user answered earlier. Building it conditionally keeps
    # the output relevant.
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

    # print() with no args emits a blank line — used here as a visual
    # separator between the three blocks.
    print(checklist)
    print(git_step)
    print(eject_step)
    print()


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def main() -> int:
    """Top-level orchestration. Return an int so main() can be used as sys.exit(main())."""

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
