# backend/_guard.py
"""
SAFETY GUARD — prevents accidental HTML/UI code being pasted into backend Python files.

What it does:
- Scans ONLY your backend project Python files (not venv, not __pycache__, not uploads).
- Ignores itself (so it never self-flags).
- Exposes run_guard() so main.py (or a pre-commit hook) can call it.

If it finds HTML markers inside backend source files, it prints an error and exits(1).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


# Keep these minimal + high-signal. We DO NOT want false positives.
BAD_MARKERS = [
    "<html>",
    "<!doctype html",
    "<body>",
    "<head>",
    "</html>",
    "<button",
]

# Directories we never want to scan.
DEFAULT_EXCLUDE_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "uploads",
    "node_modules",
    ".idea",
    ".vscode",
}

# Files we never want to scan.
DEFAULT_EXCLUDE_FILES = {
    "_guard.py",
}


def _is_excluded_path(path: Path, exclude_dirs: set[str], exclude_files: set[str]) -> bool:
    parts = set(path.parts)
    if parts & exclude_dirs:
        return True
    if path.name in exclude_files:
        return True
    return False


def _iter_backend_py_files(
    backend_dir: Path,
    exclude_dirs: set[str] | None = None,
    exclude_files: set[str] | None = None,
) -> Iterable[Path]:
    exclude_dirs = exclude_dirs or set(DEFAULT_EXCLUDE_DIRS)
    exclude_files = exclude_files or set(DEFAULT_EXCLUDE_FILES)

    # Only scan Python files under backend_dir
    for p in backend_dir.rglob("*.py"):
        if _is_excluded_path(p, exclude_dirs, exclude_files):
            continue
        yield p


def _file_has_bad_markers(path: Path) -> Tuple[bool, List[str]]:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return False, []

    hits = []
    for m in BAD_MARKERS:
        if m in txt:
            hits.append(m)
    return (len(hits) > 0), hits


def run_guard(backend_dir: str | Path | None = None) -> None:
    """
    Raises SystemExit(1) if any backend source file contains HTML markers.
    """
    bd = Path(backend_dir) if backend_dir else Path(__file__).resolve().parent
    bd = bd.resolve()

    offenders: List[Path] = []

    for py in _iter_backend_py_files(bd):
        bad, _hits = _file_has_bad_markers(py)
        if bad:
            offenders.append(py)

    if offenders:
        print("❌ SAFETY GUARD: HTML detected in backend source file(s):")
        for p in offenders:
            # print relative path if possible
            try:
                rel = p.relative_to(bd.parent)
                print(f" - {rel.as_posix()}")
            except Exception:
                print(f" - {str(p)}")

        print("\nFix: move UI/HTML into frontend files and keep backend .py pure Python.\n")
        raise SystemExit(1)


if __name__ == "__main__":
    run_guard()
    print("guard ok")