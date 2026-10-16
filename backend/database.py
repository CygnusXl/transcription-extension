"""SQLite cache for finalised transcript lines and their translations.

Only finalised lines are written, and only after they were shown live, so caching never replaces
real-time processing. Rows are keyed by video id and start time in milliseconds on the video timeline.
"""
from __future__ import annotations

import sqlite3
import time

from . import config

DB_PATH = config.DB_PATH  # tests override this

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    source_lang TEXT,
    status TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS segments (
    video_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    source_lang TEXT,
    text TEXT NOT NULL,
    PRIMARY KEY (video_id, start_ms)
);
CREATE TABLE IF NOT EXISTS translations (
    video_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    target_lang TEXT NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (video_id, start_ms, target_lang)
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def set_status(video_id: str, status: str, source_lang: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO videos(video_id, source_lang, status, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(video_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at, "
            "source_lang=COALESCE(excluded.source_lang, videos.source_lang)",
            (video_id, source_lang, status, time.time()),
        )


def save_segment(video_id: str, start_ms: int, end_ms: int, source_lang: str | None, text: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO segments(video_id, start_ms, end_ms, source_lang, text) VALUES (?,?,?,?,?) "
            "ON CONFLICT(video_id, start_ms) DO UPDATE SET end_ms=excluded.end_ms, "
            "source_lang=excluded.source_lang, text=excluded.text",
            (video_id, start_ms, end_ms, source_lang, text),
        )


def save_translation(video_id: str, start_ms: int, target_lang: str, text: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO translations(video_id, start_ms, target_lang, text) VALUES (?,?,?,?) "
            "ON CONFLICT(video_id, start_ms, target_lang) DO UPDATE SET text=excluded.text",
            (video_id, start_ms, target_lang, text),
        )


def load_segments(video_id: str, target_lang: str | None = None) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT s.start_ms, s.end_ms, s.source_lang, s.text, t.text FROM segments s "
            "LEFT JOIN translations t ON t.video_id=s.video_id AND t.start_ms=s.start_ms AND t.target_lang=? "
            "WHERE s.video_id=? ORDER BY s.start_ms",
            (target_lang or "", video_id),
        ).fetchall()
    return [
        {"start_ms": r[0], "end_ms": r[1], "source_lang": r[2], "text": r[3], "translation": r[4]} for r in rows
    ]
