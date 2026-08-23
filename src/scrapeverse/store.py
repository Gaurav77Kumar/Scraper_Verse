"""SQLite persistence + diffing between consecutive runs."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_target ON snapshots(target, collected_at);

CREATE TABLE IF NOT EXISTS healing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    healed_at TEXT NOT NULL,
    issue TEXT NOT NULL,
    recovered INTEGER NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def save_snapshot(conn: sqlite3.Connection, target: str, rows: list[dict[str, Any]]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(rows, sort_keys=True, ensure_ascii=False)
    fp = hashlib.sha256(payload.encode()).hexdigest()
    conn.execute(
        "INSERT INTO snapshots (target, collected_at, row_count, fingerprint, payload)"
        " VALUES (?, ?, ?, ?, ?)",
        (target, now, len(rows), fp, payload),
    )
    conn.commit()
    return fp


def record_healing(conn: sqlite3.Connection, target: str, issue: str, recovered: bool) -> None:
    conn.execute(
        "INSERT INTO healing_events (target, healed_at, issue, recovered) VALUES (?, ?, ?, ?)",
        (target, datetime.now(timezone.utc).isoformat(), issue, int(recovered)),
    )
    conn.commit()


def latest_snapshot(conn: sqlite3.Connection, target: str) -> tuple[str, list[dict[str, Any]]] | None:
    cur = conn.execute(
        "SELECT collected_at, payload FROM snapshots WHERE target = ?"
        " ORDER BY id DESC LIMIT 1",
        (target,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return row[0], json.loads(row[1])


def diff_rows(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> dict[str, Any]:
    """Cheap structural diff keyed by first column-ish identity of each row."""
    def key(row: dict[str, Any]) -> str:
        base = str(row.get("title") or row.get("name") or row.get("url") or sorted(row.items())[:1])
        return base.lower().strip()

    old_map = {key(r): r for r in old}
    new_map = {key(r): r for r in new}

    added = [new_map[k] for k in new_map.keys() - old_map.keys()]
    removed = [old_map[k] for k in old_map.keys() - new_map.keys()]
    changed = []
    for k in new_map.keys() & old_map.keys():
        if new_map[k] != old_map[k]:
            changed.append({"before": old_map[k], "after": new_map[k]})
    return {"added": added, "removed": removed, "changed": changed}


def has_changes(diff: dict[str, Any]) -> bool:
    return bool(diff["added"] or diff["removed"] or diff["changed"])
