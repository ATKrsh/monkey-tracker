"""
SQLite database for logging detection events.
All writes are done via a dedicated thread to keep the UI responsive.
"""
import sqlite3
import threading
import time
import os
from datetime import datetime
from typing import List, Tuple, Optional


class DetectionEvent:
    __slots__ = ("timestamp", "track_id", "label", "confidence", "x1", "y1", "x2", "y2")

    def __init__(self, track_id: int, label: str, confidence: float,
                 x1: int, y1: int, x2: int, y2: int):
        self.timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
        self.track_id = track_id
        self.label = label
        self.confidence = confidence
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2


class Database:
    """Thread-safe SQLite logger using a write queue."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._queue: List[DetectionEvent] = []
        self._conn: Optional[sqlite3.Connection] = None
        self._setup()

        self._worker = threading.Thread(target=self._flush_loop, daemon=True)
        self._worker.start()

    # ── Setup ────────────────────────────────────────────────────

    def _setup(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    track_id    INTEGER NOT NULL,
                    label       TEXT    NOT NULL,
                    confidence  REAL    NOT NULL,
                    x1 INTEGER, y1 INTEGER,
                    x2 INTEGER, y2 INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time      TEXT NOT NULL,
                    end_time        TEXT,
                    total_detections INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    # ── Public API ───────────────────────────────────────────────

    def log(self, event: DetectionEvent) -> None:
        with self._lock:
            self._queue.append(event)

    def fetch_recent(self, limit: int = 200) -> List[Tuple]:
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT timestamp, track_id, label, confidence FROM detections "
                "ORDER BY id DESC LIMIT ?", (limit,)
            )
            return cur.fetchall()

    def fetch_counts_by_minute(self, minutes: int = 60) -> List[Tuple]:
        """Returns (minute_str, count) for the last N minutes."""
        with self._get_conn() as conn:
            cur = conn.execute("""
                SELECT strftime('%H:%M', timestamp) as m, COUNT(*) as cnt
                FROM detections
                WHERE timestamp >= datetime('now', ?)
                GROUP BY m ORDER BY m
            """, (f"-{minutes} minutes",))
            return cur.fetchall()

    def total_count(self) -> int:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM detections")
            row = cur.fetchone()
            return row[0] if row else 0

    def close(self) -> None:
        self._flush()
        if self._conn:
            self._conn.close()

    # ── Internal ─────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _flush(self) -> None:
        with self._lock:
            batch = self._queue[:]
            self._queue.clear()
        if not batch:
            return
        with self._get_conn() as conn:
            conn.executemany(
                "INSERT INTO detections (timestamp,track_id,label,confidence,x1,y1,x2,y2) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(e.timestamp, e.track_id, e.label, e.confidence,
                  e.x1, e.y1, e.x2, e.y2) for e in batch]
            )
            conn.commit()

    def _flush_loop(self) -> None:
        while True:
            time.sleep(2)
            try:
                self._flush()
            except Exception:
                pass
