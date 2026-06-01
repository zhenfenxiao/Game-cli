"""TraceStore — SQLite-backed persistence for agent traces.

Stores trace sessions and events in .opengame/traces/traces.db.
Uses aiosqlite for async DB operations.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TraceStore:
    """SQLite storage for trace sessions and events.

    Schema:
        sessions: id, session_type, prompt, model, start_time, end_time,
                  success, error, metadata_json
        events: id, session_id, seq, phase, event_type, data_json, timestamp
    """

    def __init__(self, db_path: str | Path = ".opengame/traces/traces.db") -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    # --- Public API ---

    def open(self) -> None:
        """Open (or create) the database and initialize schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def create_session(
        self, prompt: str, model: str, metadata: dict[str, Any] | None = None,
        session_type: str = "generate",
    ) -> int:
        """Create a new trace session. Returns session_id."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO sessions (session_type, prompt, model, start_time, metadata_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_type, prompt, model, now, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        self._conn.commit()
        return cursor.lastrowid

    def add_event(
        self,
        session_id: int,
        seq: int,
        phase: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> int:
        """Record a single event. Returns event_id."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO events (session_id, seq, phase, event_type, data_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, seq, phase, event_type, json.dumps(data or {}, ensure_ascii=False), now),
        )
        self._conn.commit()
        return cursor.lastrowid

    def add_event_batch(self, events: list[dict[str, Any]]) -> None:
        """Insert multiple events in a single transaction."""
        if not events:
            return
        now = datetime.now(timezone.utc).isoformat()
        # Filter out events with None session_id (trace.start() not called)
        valid = [e for e in events if e.get("session_id") is not None]
        if not valid:
            return
        rows = [
            (e["session_id"], e["seq"], e["phase"], e["event_type"],
             json.dumps(e.get("data", {}), ensure_ascii=False), now)
            for e in valid
        ]
        self._conn.executemany(
            "INSERT INTO events (session_id, seq, phase, event_type, data_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def finish_session(
        self, session_id: int, success: bool, error: str | None = None,
    ) -> None:
        """Mark a session as complete."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE sessions SET end_time = ?, success = ?, error = ? WHERE id = ?",
            (now, int(success), error, session_id),
        )
        self._conn.commit()

    # --- Query API ---

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        """Get a session by ID."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,),
        ).fetchone()
        if row is None:
            return None
        # Handle both old (8 cols) and new (9 cols with session_type) schema
        if len(row) >= 9:
            return {
                "id": row[0], "session_type": row[1], "prompt": row[2],
                "model": row[3], "start_time": row[4], "end_time": row[5],
                "success": bool(row[6]), "error": row[7],
                "metadata_json": row[8],
            }
        return {
            "id": row[0], "session_type": "generate", "prompt": row[1],
            "model": row[2], "start_time": row[3], "end_time": row[4],
            "success": bool(row[5]), "error": row[6],
            "metadata_json": row[7],
        }

    # --- Shell session API ---

    def save_shell_session(
        self, session_id: int, messages: list[dict[str, Any]],
        turn_count: int, project_path: str,
    ) -> None:
        """Save shell session messages as a single event with full history.

        Uses a 'shell_snapshot' event to store the complete message history.
        """
        self.add_event(
            session_id=session_id,
            seq=0,
            phase="shell",
            event_type="shell_snapshot",
            data={
                "messages": messages,
                "turn_count": turn_count,
                "project": project_path,
            },
        )
        self._conn.execute(
            "UPDATE sessions SET end_time = ?, success = 1 WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), session_id),
        )
        self._conn.commit()

    def load_shell_session(self, session_id: int) -> dict[str, Any] | None:
        """Load shell session messages from a saved session."""
        rows = self._conn.execute(
            "SELECT data_json FROM events WHERE session_id = ? "
            "AND event_type = 'shell_snapshot' ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchall()
        if not rows:
            return None
        data = json.loads(rows[0][0])
        return {
            "messages": data.get("messages", []),
            "turn_count": data.get("turn_count", 0),
            "project": data.get("project", ""),
        }

    def list_shell_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent shell sessions with message counts."""
        rows = self._conn.execute(
            "SELECT s.id, s.prompt, s.model, s.start_time, s.success, "
            "(SELECT COUNT(*) FROM events WHERE session_id = s.id "
            " AND event_type = 'shell_snapshot') "
            "FROM sessions s WHERE s.session_type = 'shell' "
            "ORDER BY s.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "prompt": r[1][:80], "model": r[2],
             "start": r[3], "has_snapshot": bool(r[4]), "saved": bool(r[5])}
            for r in rows
        ]

    def get_events(self, session_id: int) -> list[dict[str, Any]]:
        """Get all events for a session, ordered by seq."""
        rows = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [
            {"id": r[0], "session_id": r[1], "seq": r[2], "phase": r[3],
             "event_type": r[4], "data_json": r[5], "timestamp": r[6]}
            for r in rows
        ]

    def list_sessions(self, limit: int = 20, session_type: str | None = None) -> list[dict[str, Any]]:
        """List recent sessions, optionally filtered by type."""
        if session_type:
            rows = self._conn.execute(
                "SELECT id, session_type, prompt, model, start_time, end_time, success "
                "FROM sessions WHERE session_type = ? ORDER BY id DESC LIMIT ?",
                (session_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, session_type, prompt, model, start_time, end_time, success "
                "FROM sessions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": r[0], "type": r[1], "prompt": r[2][:80], "model": r[3],
             "start": r[4], "end": r[5], "success": bool(r[6])}
            for r in rows
        ]

    # --- Export API ---

    def export_session(self, session_id: int) -> dict[str, Any] | None:
        """Export a single session with all events as a JSON-serializable dict."""
        session = self.get_session(session_id)
        if session is None:
            return None

        events = self.get_events(session_id)
        # Parse data_json for each event
        parsed_events = []
        for e in events:
            e["data"] = json.loads(e["data_json"]) if isinstance(e["data_json"], str) else e.get("data_json", {})
            e.pop("data_json", None)
            parsed_events.append(e)

        session["metadata"] = json.loads(session["metadata_json"]) if isinstance(session["metadata_json"], str) else session.get("metadata_json", {})
        session.pop("metadata_json", None)

        return {"session": session, "events": parsed_events}

    def export_all(self) -> list[dict[str, Any]]:
        """Export all sessions with events as JSON-serializable dicts."""
        sessions = self.list_sessions(limit=10000)
        return [
            export for s in sessions
            if (export := self.export_session(s["id"])) is not None
        ]

    # --- Schema ---

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_type TEXT NOT NULL DEFAULT 'generate',
                prompt TEXT NOT NULL,
                model TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                success INTEGER DEFAULT 0,
                error TEXT,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        # Migrate existing tables: add session_type column if missing
        try:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN session_type TEXT NOT NULL DEFAULT 'generate'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                seq INTEGER NOT NULL,
                phase TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data_json TEXT DEFAULT '{}',
                timestamp TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)
        """)
        self._conn.commit()
