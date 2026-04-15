"""Eject boilerplate-only machinery from the repo.

Run via `make eject` (or `python scripts/eject.py`). This removes files
and Makefile targets that only exist to bootstrap the boilerplate, leaving
a clean project behind.

Run this AFTER `make init` and after you've verified (with `make check` or
a quick smoke test) that the initialized boilerplate looks the way you want
it to. Ejecting is one-way — rerunning it is a no-op, but there's no undo.

What gets removed:
  * scripts/init_boilerplate.py
  * scripts/eject.py              (this file — deleted last)
  * scripts/                      (if empty after the deletes above)
  * `init` / `eject` targets from the Makefile
  * `init` / `eject` from the Makefile's .PHONY line
  * `init` / `eject` from the help target's echo block
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
MAKEFILE = REPO_ROOT / "Makefile"

# Ordered: init_boilerplate first, this file last. eject.py must be the
# final file touched — no filesystem work after it self-unlinks.
FILES_TO_DELETE = [
    SCRIPTS_DIR / "init_boilerplate.py",
    SCRIPTS_DIR / "eject.py",
]

TARGETS_TO_STRIP = ("init", "eject")


# --------------------------------------------------------------------------- #
# 1. CLI                                                                      #
# --------------------------------------------------------------------------- #


def parse_args() -> argparse.Namespace:
    """Parse command-line flags."""

    parser = argparse.ArgumentParser(description="Remove boilerplate-only machinery from the repo.")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be removed without touching the filesystem",
    )

    return parser.parse_args()


# --------------------------------------------------------------------------- #
# 2. File deletion                                                            #
# --------------------------------------------------------------------------- #


def delete_boilerplate_files(*, dry_run: bool) -> None:
    """Delete the boilerplate scripts, then remove scripts/ if it's empty."""

    for path in FILES_TO_DELETE:
        if not path.exists():
            print(f"already gone: {path.relative_to(REPO_ROOT)}")
            continue

        if dry_run:
            print(f"would delete: {path.relative_to(REPO_ROOT)}")
            continue

        path.unlink()
        print(f"deleted: {path.relative_to(REPO_ROOT)}")

    # Only remove scripts/ if empty — never use shutil.rmtree() here, we
    # must not clobber anything the user has added to the directory.
    if SCRIPTS_DIR.exists() and not any(SCRIPTS_DIR.iterdir()):
        if dry_run:
            print(f"would remove empty dir: {SCRIPTS_DIR.relative_to(REPO_ROOT)}")
        else:
            SCRIPTS_DIR.rmdir()
            print(f"removed empty dir: {SCRIPTS_DIR.relative_to(REPO_ROOT)}")


# --------------------------------------------------------------------------- #
# 3. Makefile surgery                                                         #
# --------------------------------------------------------------------------- #


def strip_makefile_targets(*, dry_run: bool) -> None:
    """Remove the init/eject targets, .PHONY entries, and help lines.

    Three cases are handled:

      1. The `.PHONY:` line keeps its prefix but drops the init/eject tokens.
      2. `@echo "  init ..."` / `@echo "  eject ..."` help lines are dropped.
      3. Target blocks (header + indented recipe + trailing blank) are
         consumed in one step.
    """

    original_text = MAKEFILE.read_text(encoding="utf-8")
    lines = original_text.splitlines(keepends=True)

    kept: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        if stripped.startswith(".PHONY:"):
            prefix, _, targets = line.partition(":")
            tokens = targets.split()
            cleaned_tokens = [t for t in tokens if t not in TARGETS_TO_STRIP]
            kept.append(f"{prefix}: {' '.join(cleaned_tokens)}\n")
            i += 1
            continue

        if stripped.startswith('@echo "  init') or stripped.startswith('@echo "  eject'):
            i += 1
            continue

        is_target_header = any(stripped.startswith(f"{name}:") for name in TARGETS_TO_STRIP)
        if is_target_header and not line.startswith((" ", "\t")):
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                if not lines[i].startswith((" ", "\t")):
                    break
                i += 1
            # Swallow the separator blank so we don't leave a double-blank.
            if i < len(lines) and lines[i].strip() == "":
                i += 1
            continue

        kept.append(line)
        i += 1

    new_text = "".join(kept)

    if new_text == original_text:
        print("Makefile already clean, skipping")
        return

    lines_removed = len(lines) - len(kept)

    if dry_run:
        print(f"would rewrite Makefile ({lines_removed} lines removed)")
    else:
        MAKEFILE.write_text(new_text, encoding="utf-8")
        print(f"rewrote Makefile ({lines_removed} lines removed)")


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def main() -> int:
    """Top-level orchestration.

    ORDER MATTERS: strip_makefile_targets runs FIRST, because
    delete_boilerplate_files unlinks this script as its final action.
    """

    args = parse_args()

    print("Ejecting boilerplate scaffolding...")
    if args.dry_run:
        print("(dry run — no files will be modified)")
    print()

    strip_makefile_targets(dry_run=args.dry_run)
    delete_boilerplate_files(dry_run=args.dry_run)

    print()
    print("Done. Any leftover boilerplate docs can be removed manually.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
