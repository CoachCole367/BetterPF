import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path(os.getenv("BETTERPF_DB", "betterpf.db"))


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings_cache (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )


def load_cache() -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT updated_at, payload FROM listings_cache WHERE id = 1"
        ).fetchone()
        if not row:
            return None
        updated_at, payload = row
        return {"updated_at": updated_at, "payload": json.loads(payload)}


def save_cache(items: Any, updated_at: str) -> None:
    payload = json.dumps(items)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO listings_cache (id, updated_at, payload)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at,
                payload = excluded.payload
            """,
            (updated_at, payload),
        )
