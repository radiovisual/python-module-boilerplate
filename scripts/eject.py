"""Eject boilerplate-only machinery from the repo.

Run via `make eject` (or `python scripts/eject.py`). This removes files
and Makefile targets that only exist to bootstrap the boilerplate, leaving
a clean project behind.

Run this AFTER `make init` and after you've verified (with `make check` or
a quick smoke test) that the initialized boilerplate looks the way you want
it to. Ejecting is one-way — rerunning it is a no-op, but there's no undo.

------------------------------------------------------------------------
What gets removed
------------------------------------------------------------------------
  * scripts/init_boilerplate.py
  * scripts/eject.py              (this file — deleted last)
  * scripts/                      (if empty after the deletes above)
  * `init` / `eject` targets from the Makefile
  * `init` / `eject` from the Makefile's .PHONY line
  * `init` / `eject` from the help target's echo block

A note about deleting your own running script: Python loads the .py file
into memory once at import/exec time and then closes the file handle. So
`Path(__file__).unlink()` is safe — the interpreter doesn't need the file
on disk anymore. Just do it LAST, and don't try to touch the file again
after the unlink.
------------------------------------------------------------------------
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

# Ordered: init_boilerplate first, this file last. Order matters because
# once this file is unlinked, we can't do any more disk work on it.
FILES_TO_DELETE = [
    SCRIPTS_DIR / "init_boilerplate.py",
    SCRIPTS_DIR / "eject.py",
]

# Makefile target names that need to be stripped.
TARGETS_TO_STRIP = ("init", "eject")


# --------------------------------------------------------------------------- #
# 1. CLI                                                                      #
# --------------------------------------------------------------------------- #


def parse_args() -> argparse.Namespace:
    """Parse command-line flags. We only support --dry-run."""

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

    # Walk the list of files we've been told to delete. FILES_TO_DELETE
    # is ordered so init_boilerplate.py gets unlinked BEFORE this script
    # itself — we can't rely on file access after self-unlink.
    for path in FILES_TO_DELETE:
        # Path.exists() returns False for both "missing" and "broken
        # symlink". We use it here so re-running eject is idempotent:
        # if a file was already deleted on a previous run, we just
        # note it and move on rather than crashing.
        if not path.exists():
            print(f"already gone: {path.relative_to(REPO_ROOT)}")
            continue

        # Dry run: announce but don't touch the disk. This is how the
        # user previews eject's effect before committing to it.
        if dry_run:
            print(f"would delete: {path.relative_to(REPO_ROOT)}")
            continue

        # Real run: actually unlink the file. Path.unlink() is pathlib's
        # name for `os.remove()` — it deletes a single file. There's a
        # `missing_ok=True` kwarg (Python 3.8+) that would let us skip
        # the `.exists()` check above, but explicit is clearer here.
        #
        # Note: unlinking the currently-running Python script is safe.
        # CPython loads the .py file into memory at import/exec time and
        # closes the handle, so the interpreter doesn't need the file on
        # disk anymore. Just don't try to touch the file again after this.
        path.unlink()
        print(f"deleted: {path.relative_to(REPO_ROOT)}")

    # After deleting the known boilerplate files, check whether the
    # scripts/ directory is now empty. If it is, rmdir it for cleanliness.
    # If the user added their own scripts, leave the directory alone —
    # we don't want to force-delete user content.
    #
    # The "is this dir empty?" idiom: Path.iterdir() yields child paths,
    # and `any(...)` on an iterable returns True if any element exists.
    # So `not any(path.iterdir())` is True iff the directory is empty.
    # (TS analog: fs.readdirSync(path).length === 0)
    #
    # We guard with .exists() first because scripts/ might have been
    # removed manually, or might never have existed in a weird repo state.
    if SCRIPTS_DIR.exists() and not any(SCRIPTS_DIR.iterdir()):
        if dry_run:
            print(f"would remove empty dir: {SCRIPTS_DIR.relative_to(REPO_ROOT)}")
        else:
            # Path.rmdir() is strict — it only works on empty directories
            # and raises OSError otherwise. That's exactly what we want:
            # it enforces the "don't stomp on user content" guarantee.
            # Contrast with shutil.rmtree() which recursively deletes
            # everything and would be dangerous here.
            SCRIPTS_DIR.rmdir()
            print(f"removed empty dir: {SCRIPTS_DIR.relative_to(REPO_ROOT)}")


# --------------------------------------------------------------------------- #
# 3. Makefile surgery                                                         #
# --------------------------------------------------------------------------- #


def strip_makefile_targets(*, dry_run: bool) -> None:
    """Remove the init/eject targets, .PHONY entries, and help lines.

    Makefile parsing from scratch is a rabbit hole, but the structure of
    this project's Makefile is simple enough that we can do a line-by-line
    transformation without needing a real parser.
    """

    # Read the whole Makefile as one string. encoding="utf-8" is explicit
    # because Python's default is platform-dependent (gotcha on Windows).
    original_text = MAKEFILE.read_text(encoding="utf-8")

    # splitlines(keepends=True) splits on line boundaries but KEEPS the
    # trailing newlines on each element. This matters for reassembly: if
    # we drop the newlines, "".join(...) would produce a single blob with
    # no line breaks. (TS analog: str.split(/(?<=\n)/) — clunkier.)
    lines = original_text.splitlines(keepends=True)

    # Accumulator for the lines we want to keep. We walk the input with
    # an explicit index (not a for-each) because when we hit a target
    # block we need to skip AHEAD across multiple lines — a plain
    # `for line in lines` loop doesn't let you do that cleanly.
    kept: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # --- Case 1: top-of-file .PHONY declaration --------------------
        # The Makefile starts with:
        #   .PHONY: help init eject install hooks lint format typecheck test check clean
        # We want to keep the line but strip out the "init" and "eject" tokens.
        #
        # We detect it with startswith, then split on whitespace, filter
        # out the unwanted tokens, and rejoin. `split()` with no argument
        # splits on any run of whitespace and drops empties — the right
        # default for simple token lists like this.
        if stripped.startswith(".PHONY:"):
            # Preserve the original indentation (should be zero here, but
            # being careful). We split the content after ".PHONY:", not
            # the whole line, to avoid losing the prefix.
            prefix, _, targets = line.partition(":")
            tokens = targets.split()
            cleaned_tokens = [t for t in tokens if t not in TARGETS_TO_STRIP]
            kept.append(f"{prefix}: {' '.join(cleaned_tokens)}\n")
            i += 1
            continue

        # --- Case 2: help-target echo lines ----------------------------
        # The help target prints:
        #   @echo "  init       Interactively customize the boilerplate ..."
        # We want to drop these two lines entirely. Matching on the
        # stripped form handles the leading tab from make indentation.
        if stripped.startswith('@echo "  init') or stripped.startswith('@echo "  eject'):
            i += 1
            continue

        # --- Case 3: target blocks -------------------------------------
        # A target block looks like:
        #   init:
        #       $(PYTHON) scripts/init_boilerplate.py $(ARGS)
        #
        # The header line is flush-left and starts with "init:" or "eject:".
        # Recipe lines underneath are indented with a tab (make's rule).
        # The block ends at the first blank line OR another flush-left
        # target header.
        is_target_header = any(stripped.startswith(f"{name}:") for name in TARGETS_TO_STRIP)
        if is_target_header and not line.startswith((" ", "\t")):
            # Skip the header line itself.
            i += 1
            # Skip the recipe body: indented lines until blank/EOF.
            while i < len(lines) and lines[i].strip() != "":
                if not lines[i].startswith((" ", "\t")):
                    # Hit a new flush-left line — not part of our block.
                    break
                i += 1
            # Also swallow the blank separator line so we don't leave
            # a double-blank where the target used to be.
            if i < len(lines) and lines[i].strip() == "":
                i += 1
            continue

        # --- Default: keep the line --------------------------------
        kept.append(line)
        i += 1

    # Reassemble the kept lines into a single string. "".join is the
    # standard Python idiom for concatenating a list of strings — it's
    # linear-time and way faster than `result += line` in a loop.
    new_text = "".join(kept)

    # If nothing actually changed (eject was already run, or the Makefile
    # never had these targets), skip the write to avoid bumping mtimes.
    if new_text == original_text:
        print("Makefile already clean, skipping")
        return

    # Report the diff size. Counting lines is a rough but useful signal
    # for dry-run previews.
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

    ORDER MATTERS: strip_makefile_targets runs FIRST, then
    delete_boilerplate_files. The reason is that delete_boilerplate_files
    unlinks THIS VERY SCRIPT as its last action, and we need the Makefile
    surgery to be committed to disk before that happens.

    Python will happily continue executing in-memory bytecode after the
    source file is unlinked — CPython only needs the .py file at import
    time, not at runtime. So `return 0` still works even after self-unlink.
    But any code that tries to read or write files after the unlink is
    on thin ice, so we keep the "do stuff with other files first, delete
    self last" discipline.
    """

    args = parse_args()

    print("Ejecting boilerplate scaffolding...")
    if args.dry_run:
        print("(dry run — no files will be modified)")
    print()

    # Step 1: rewrite the Makefile (while this script still exists).
    strip_makefile_targets(dry_run=args.dry_run)

    # Step 2: delete boilerplate files. init_boilerplate.py first, then
    # this script last. After the final unlink, we're still in memory
    # and can finish executing normally — just don't touch the filesystem.
    delete_boilerplate_files(dry_run=args.dry_run)

    print()
    print("Done. Any leftover boilerplate docs can be removed manually.")

    # Returning an int lets main() pair with sys.exit(main()) — exit
    # code 0 means success. Returning nothing (None) would be treated
    # as 0 by sys.exit() but the explicit return is clearer.
    return 0


if __name__ == "__main__":
    sys.exit(main())
