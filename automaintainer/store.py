from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, filename: str):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(filename)
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, item TEXT, project TEXT, status TEXT, detail TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self.db.commit()

    def record(self, item: str, project: str, status: str, detail: Any) -> None:
        self.db.execute("INSERT INTO runs(item,project,status,detail) VALUES(?,?,?,?)", (item, project, status, json.dumps(detail, ensure_ascii=False)))
        self.db.commit()

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        self.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        self.db.commit()

    def latest_status(self, item: str) -> str | None:
        row = self.db.execute("SELECT status FROM runs WHERE item=? ORDER BY id DESC LIMIT 1", (item,)).fetchone()
        return row[0] if row else None

    def escalations(self) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM runs WHERE status='escalated' ORDER BY id DESC LIMIT 100").fetchall()
        return [dict(row) for row in rows]
