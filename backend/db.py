# backend/db.py
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_PATH = Path(__file__).resolve().parent / "followthrough.db"


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
              id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS uploads (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL,
              filename TEXT NOT NULL,
              audio_path TEXT NOT NULL,
              created_at TEXT NOT NULL,
              reprocessed_at TEXT,
              FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS actions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              upload_id TEXT NOT NULL,
              idx INTEGER NOT NULL,
              action_text TEXT,
              owner TEXT,
              deadline TEXT,
              source_sentence TEXT,
              confidence REAL,
              dedupe_key TEXT,
              FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_actions_upload_idx ON actions(upload_id, idx);
            CREATE INDEX IF NOT EXISTS idx_actions_upload_dedupe ON actions(upload_id, dedupe_key);

            CREATE TABLE IF NOT EXISTS approvals (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              workspace_id TEXT NOT NULL,
              dedupe_key TEXT NOT NULL,
              upload_id TEXT,
              action_idx INTEGER,
              action_text TEXT NOT NULL,
              deadline TEXT NOT NULL,
              event_id TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(workspace_id, dedupe_key),
              FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_approvals_ws ON approvals(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_approvals_event ON approvals(event_id);

            CREATE TABLE IF NOT EXISTS google_tokens (
              workspace_id TEXT PRIMARY KEY,
              token_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );
            """
        )

        # Safe migrations for existing Railway DBs
        if not _column_exists(conn, "uploads", "status"):
            conn.execute("ALTER TABLE uploads ADD COLUMN status TEXT NOT NULL DEFAULT 'uploaded'")

        if not _column_exists(conn, "uploads", "error_message"):
            conn.execute("ALTER TABLE uploads ADD COLUMN error_message TEXT")

        if not _column_exists(conn, "uploads", "transcript"):
            conn.execute("ALTER TABLE uploads ADD COLUMN transcript TEXT")

        if not _column_exists(conn, "uploads", "summary_json"):
            conn.execute("ALTER TABLE uploads ADD COLUMN summary_json TEXT")


def ensure_workspace(workspace_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO workspaces(id, created_at) VALUES (?, ?)",
            (workspace_id, _now_iso()),
        )


# ---------------- Uploads / Status ----------------
def create_upload_record(workspace_id: str, upload_id: str, filename: str, audio_path: str) -> None:
    ensure_workspace(workspace_id)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO uploads(
                id, workspace_id, filename, audio_path, created_at, reprocessed_at, status, error_message, transcript, summary_json
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL)
            """,
            (upload_id, workspace_id, filename, audio_path, _now_iso(), "uploaded"),
        )


def set_upload_status(upload_id: str, status: str, error_message: Optional[str] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE uploads SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, upload_id),
        )


def save_upload_result(
    upload_id: str,
    transcript: str,
    summary_json: str,
    actions: List[Dict[str, Any]],
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE uploads
            SET transcript = ?, summary_json = ?, status = ?, error_message = NULL
            WHERE id = ?
            """,
            (transcript, summary_json, "completed", upload_id),
        )

        conn.execute("DELETE FROM actions WHERE upload_id = ?", (upload_id,))

        for i, a in enumerate(actions or []):
            if not isinstance(a, dict):
                continue

            conn.execute(
                """
                INSERT INTO actions(
                  upload_id, idx, action_text, owner, deadline, source_sentence, confidence, dedupe_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    int(i),
                    (a.get("action") or "").strip() or None,
                    (a.get("owner") or None),
                    (a.get("deadline") or None),
                    (a.get("source_sentence") or None),
                    float(a.get("confidence")) if a.get("confidence") is not None else None,
                    (a.get("dedupe_key") or None),
                ),
            )


def save_upload(
    workspace_id: str,
    upload_id: str,
    filename: str,
    audio_path: str,
    actions: List[Dict[str, Any]],
) -> None:
    ensure_workspace(workspace_id)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO uploads(
                id, workspace_id, filename, audio_path, created_at, reprocessed_at, status, error_message, transcript, summary_json
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL)
            """,
            (upload_id, workspace_id, filename, audio_path, _now_iso(), "completed"),
        )

        for i, a in enumerate(actions or []):
            if not isinstance(a, dict):
                continue

            conn.execute(
                """
                INSERT INTO actions(
                  upload_id, idx, action_text, owner, deadline, source_sentence, confidence, dedupe_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    int(i),
                    (a.get("action") or "").strip() or None,
                    (a.get("owner") or None),
                    (a.get("deadline") or None),
                    (a.get("source_sentence") or None),
                    float(a.get("confidence")) if a.get("confidence") is not None else None,
                    (a.get("dedupe_key") or None),
                ),
            )


def overwrite_actions(upload_id: str, actions: List[Dict[str, Any]]) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM actions WHERE upload_id = ?", (upload_id,))

        for i, a in enumerate(actions or []):
            if not isinstance(a, dict):
                continue

            conn.execute(
                """
                INSERT INTO actions(
                  upload_id, idx, action_text, owner, deadline, source_sentence, confidence, dedupe_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    int(i),
                    (a.get("action") or "").strip() or None,
                    (a.get("owner") or None),
                    (a.get("deadline") or None),
                    (a.get("source_sentence") or None),
                    float(a.get("confidence")) if a.get("confidence") is not None else None,
                    (a.get("dedupe_key") or None),
                ),
            )


def set_upload_reprocessed(upload_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE uploads SET reprocessed_at = ? WHERE id = ?", (_now_iso(), upload_id))


def latest_upload_id(workspace_id: str) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM uploads WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 1",
            (workspace_id,),
        ).fetchone()
        return str(row["id"]) if row else None


def get_upload(workspace_id: str, upload_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM uploads WHERE id = ? AND workspace_id = ?",
            (upload_id, workspace_id),
        ).fetchone()
        return dict(row) if row else None


def get_upload_status(workspace_id: str, upload_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, workspace_id, filename, created_at, status, error_message, transcript, summary_json
            FROM uploads
            WHERE id = ? AND workspace_id = ?
            """,
            (upload_id, workspace_id),
        ).fetchone()

        return dict(row) if row else None


def get_actions(upload_id: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT idx, action_text, owner, deadline, source_sentence, confidence, dedupe_key
            FROM actions WHERE upload_id = ? ORDER BY idx ASC
            """,
            (upload_id,),
        ).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "action": r["action_text"],
                    "owner": r["owner"],
                    "deadline": r["deadline"],
                    "source_sentence": r["source_sentence"],
                    "confidence": r["confidence"],
                    "dedupe_key": r["dedupe_key"] or "",
                }
            )

        return out


# ---------------- Approvals ----------------
def get_approvals_map(workspace_id: str) -> Dict[str, Any]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT dedupe_key, action_text, deadline, event_id, action_idx, upload_id, created_at
            FROM approvals WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchall()

        m: Dict[str, Any] = {}
        for r in rows:
            m[str(r["dedupe_key"])] = {
                "action": r["action_text"],
                "deadline": r["deadline"],
                "event_id": r["event_id"],
                "index": r["action_idx"],
                "upload_id": r["upload_id"],
                "created_at": r["created_at"],
            }

        return m


def reset_approvals(workspace_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM approvals WHERE workspace_id = ?", (workspace_id,))


def insert_approval(
    workspace_id: str,
    dedupe_key: str,
    upload_id: str,
    action_idx: int,
    action_text: str,
    deadline: str,
    event_id: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO approvals(
              workspace_id, dedupe_key, upload_id, action_idx, action_text, deadline, event_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, dedupe_key, upload_id, int(action_idx), action_text, deadline, event_id, _now_iso()),
        )


def delete_approval(workspace_id: str, dedupe_key: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM approvals WHERE workspace_id = ? AND dedupe_key = ?",
            (workspace_id, dedupe_key),
        )
        return cur.rowcount > 0


# ---------------- Google tokens ----------------
def set_google_token(workspace_id: str, token_json: str) -> None:
    ensure_workspace(workspace_id)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO google_tokens(workspace_id, token_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
              token_json=excluded.token_json,
              updated_at=excluded.updated_at
            """,
            (workspace_id, token_json, _now_iso()),
        )


def get_google_token(workspace_id: str) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT token_json FROM google_tokens WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        return str(row["token_json"]) if row else None


def delete_google_token(workspace_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM google_tokens WHERE workspace_id = ?", (workspace_id,))


def google_connected(workspace_id: str) -> bool:
    return get_google_token(workspace_id) is not None