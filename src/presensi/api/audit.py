"""Audit log verify — SQLite append-only.

Sesuai DESAIN §7: record presensi resmi diturunkan dari log server, bukan
klaim app. Tidak ada UPDATE/DELETE — hanya INSERT dan SELECT (query analisis).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS verify_log (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  ts            TEXT NOT NULL,
  claimed_user  TEXT,
  verdict_user  TEXT,
  status        TEXT NOT NULL,
  confidence    REAL,
  frames_valid  INTEGER NOT NULL,
  frames_total  INTEGER NOT NULL,
  model_version TEXT NOT NULL,
  meta          TEXT
);
"""


class AuditLog:
    def __init__(self, data_dir: Path | str):
        self.db_path = Path(data_dir) / "audit.db"
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, claimed_user: str | None, verdict: dict,
               model_version: str, meta: dict | None = None) -> None:
        self._conn.execute(
            "INSERT INTO verify_log (ts, claimed_user, verdict_user, status,"
            " confidence, frames_valid, frames_total, model_version, meta)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (time.strftime("%Y-%m-%dT%H:%M:%S"),
             claimed_user, verdict.get("user_id"), verdict["status"],
             verdict.get("confidence"), int(verdict.get("frames_valid") or 0),
             int(verdict.get("frames_total") or 0), model_version,
             json.dumps(meta, ensure_ascii=False) if meta else None))
        self._conn.commit()

    def recent(self, limit: int = 50) -> list[dict]:
        cur = self._conn.execute(
            "SELECT id, ts, claimed_user, verdict_user, status, confidence,"
            " frames_valid, frames_total, model_version, meta FROM verify_log"
            " ORDER BY id DESC LIMIT ?", (int(limit),))
        keys = ["id", "ts", "claimed_user", "verdict_user", "status",
                "confidence", "frames_valid", "frames_total", "model_version",
                "meta"]
        return [dict(zip(keys, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
