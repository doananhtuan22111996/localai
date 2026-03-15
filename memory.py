"""
memory.py — Session memory with SQLite
Persist conversation history across sessions.
"""
from __future__ import annotations

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".config" / "localai" / "sessions.db"


def _get_connection() -> sqlite3.Connection:
    """Get a SQLite connection, creating the DB and tables if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    conn.commit()
    return conn


def create_session(name: str | None = None) -> str:
    """Create a new session. Returns session ID."""
    conn = _get_connection()
    session_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    if not name:
        name = f"session-{now[:10]}-{session_id[:6]}"
    conn.execute(
        "INSERT INTO sessions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (session_id, name, now, now),
    )
    conn.commit()
    conn.close()
    return session_id


def list_sessions(limit: int = 20) -> list[dict]:
    """List recent sessions."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT id, name, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_session_id() -> str | None:
    """Get the most recently updated session ID."""
    conn = _get_connection()
    row = conn.execute(
        "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def save_message(session_id: str, message: dict):
    """Save a single message to a session."""
    conn = _get_connection()
    now = datetime.now().isoformat()
    tool_calls = json.dumps(message.get("tool_calls")) if message.get("tool_calls") else None
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, message["role"], message.get("content"), tool_calls, message.get("tool_call_id"), now),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    conn.commit()
    conn.close()


def load_messages(session_id: str, limit: int = 50) -> list[dict]:
    """Load messages from a session."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT role, content, tool_calls, tool_call_id FROM messages "
        "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()

    messages = []
    for row in reversed(rows):  # Reverse to get chronological order
        msg = {"role": row["role"]}
        if row["content"] is not None:
            msg["content"] = row["content"]
        if row["tool_calls"]:
            msg["tool_calls"] = json.loads(row["tool_calls"])
        if row["tool_call_id"]:
            msg["tool_call_id"] = row["tool_call_id"]
        messages.append(msg)
    return messages


def delete_session(session_id: str):
    """Delete a session and its messages."""
    conn = _get_connection()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
