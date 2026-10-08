"""SQLite cache for transcripts and translations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cache.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT NOT NULL,
    source_lang TEXT,
    target_lang TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    PRIMARY KEY (video_id, target_lang)
);
CREATE TABLE IF NOT EXISTS segments (
    video_id TEXT NOT NULL,
    seg_id INTEGER NOT NULL,
    start_s REAL NOT NULL,
    end_s REAL NOT NULL,
    text TEXT NOT NULL,
    translation TEXT,
    target_lang TEXT,
    PRIMARY KEY (video_id, seg_id, target_lang)
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
