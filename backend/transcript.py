"""Transcript store for one session: keeps ordered segments and merges updates by id."""
from __future__ import annotations

from .streaming_asr import Segment


class Transcript:
    def __init__(self) -> None:
        self._segments: dict[int, Segment] = {}

    def upsert(self, seg: Segment) -> None:
        self._segments[seg.id] = seg

    def ordered(self) -> list[Segment]:
        return sorted(self._segments.values(), key=lambda s: s.start)
