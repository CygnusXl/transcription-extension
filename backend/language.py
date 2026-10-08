"""Language detection (Stage 5 - not implemented yet).

Whisper reports a detected language per window; this module will smooth it over time and
fall back to the user's manual selection.
"""
from __future__ import annotations

SUPPORTED = {"en", "id", "ja", "ko", "zh", "es", "de"}


def normalize(lang: str | None) -> str | None:
    if not lang or lang == "auto":
        return None
    return lang if lang in SUPPORTED else None
