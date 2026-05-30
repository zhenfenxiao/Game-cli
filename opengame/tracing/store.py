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
        sessions: id, prompt, model, start_time, end_time, success, error
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
    ) -> int:
        """Create a new trace session. Returns session_id."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO sessions (prompt, model, start_time, metadata_json) VALUES (?, ?, ?, ?)",
            (prompt, model, now, json.dumps(metadata or {}, ensure_ascii=False)),
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
        return {
            "id": row[0], "prompt": row[1], "model": row[2],
            "start_time": row[3], "end_time": row[4],
            "success": bool(row[5]), "error": row[6],
            "metadata_json": row[7],
        }

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

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent sessions."""
        rows = self._conn.execute(
            "SELECT id, prompt, model, start_time, end_time, success "
            "FROM sessions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "prompt": r[1][:80], "model": r[2],
             "start": r[3], "end": r[4], "success": bool(r[5])}
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
                prompt TEXT NOT NULL,
                model TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                success INTEGER DEFAULT 0,
                error TEXT,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
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
