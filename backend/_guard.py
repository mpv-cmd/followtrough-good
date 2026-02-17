# backend/_guard.py
"""
FollowThrough Safety Guard (Option A)

- Scan ONLY git-tracked backend *.py files (so venv/site-packages won't trigger)
- Also scan STAGED backend *.py files (what you're about to commit)
- IMPORTANT: do NOT scan this file itself, otherwise it can self-flag
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Iterable, List, Set

BACKEND_DIR = pathlib.Path(__file__).resolve().parent
SELF_PATH = pathlib.Path(__file__).resolve()


# Build markers without embedding raw "<html>" etc in this file (avoid self-triggering).
_lt = "<"
_gt = ">"
BAD_MARKERS = [
    _lt + "html" + _gt,
    "<!" + "doctype html",
    _lt + "body" + _gt,
    _lt + "head" + _gt,
    _lt + "button" + _gt,
    _lt + "script" + _gt,
    _lt + "style" + _gt,
    _lt + "/html" + _gt,
    # Extra UI-ish patterns built dynamically so they don't match this file literally
    "." + "wrap" + "{",
    "document" + "." + "addEventListener(",
    "window" + "." + "addEventListener(",
]


def _run_git(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(BACKEND_DIR.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _is_git_repo() -> bool:
    p = _run_git(["rev-parse", "--is-inside-work-tree"])
    return p.returncode == 0 and p.stdout.strip() == "true"


def _repo_root() -> pathlib.Path:
    p = _run_git(["rev-parse", "--show-toplevel"])
    if p.returncode != 0:
        return BACKEND_DIR.parent
    return pathlib.Path(p.stdout.strip()).resolve()


def _tracked_backend_py_files() -> List[pathlib.Path]:
    """Git-tracked *.py under backend/."""
    root = _repo_root()
    backend_rel = BACKEND_DIR.relative_to(root)

    p = _run_git(["ls-files", str(backend_rel)])
    if p.returncode != 0:
        return []

    out: List[pathlib.Path] = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".py"):
            continue
        path = (root / line).resolve()
        if path.is_file() and (BACKEND_DIR in path.parents):
            out.append(path)
    return out


def _staged_backend_py_files() -> List[pathlib.Path]:
    """Staged *.py under backend/ (ACMR)."""
    if not _is_git_repo():
        return []

    root = _repo_root()
    backend_rel = BACKEND_DIR.relative_to(root)

    p = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if p.returncode != 0:
        return []

    out: List[pathlib.Path] = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".py"):
            continue
        rel = pathlib.Path(line)
        if backend_rel not in rel.parents and rel != backend_rel:
            continue
        path = (root / rel).resolve()
        if path.is_file() and (BACKEND_DIR in path.parents):
            out.append(path)
    return out


def _scan_files(files: Iterable[pathlib.Path]) -> List[pathlib.Path]:
    bad: List[pathlib.Path] = []
    for py in files:
        py = py.resolve()

        # ✅ critical: never scan this guard file
        if py == SELF_PATH:
            continue

        try:
            txt = py.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue

        if any(m.lower() in txt for m in BAD_MARKERS):
            bad.append(py)
    return bad


def run_guard() -> None:
    files = _tracked_backend_py_files()
    files += _staged_backend_py_files()

    # Unique + stable order
    uniq: List[pathlib.Path] = []
    seen: Set[pathlib.Path] = set()
    for f in files:
        rf = f.resolve()
        if rf not in seen:
            seen.add(rf)
            uniq.append(rf)

    bad = _scan_files(uniq)
    if bad:
        root = _repo_root()
        print("❌ SAFETY GUARD: HTML detected in backend source file(s):")
        for p in bad:
            try:
                print(f" - {p.relative_to(root)}")
            except Exception:
                print(f" - {p}")
        print("\nFix: move UI/HTML into frontend files and keep backend .py pure Python.\n")
        sys.exit(1)


if __name__ == "__main__":
    run_guard()