"""Groups streaming words into display lines and produces id-stable updates.

A line is "open" while it is still being spoken: it is sent repeatedly as a partial (final=False)
and replaced in place (same id) until it is closed as final (final=True). The client upserts by id.
An update with empty text means "remove this partial line".
"""
from __future__ import annotations

from dataclasses import dataclass

from .streaming_asr import Word, join_words

SENTENCE_END = ".?!。？！…‼⁇"


@dataclass
class Update:
    id: int
    start: float
    end: float
    text: str
    final: bool


class LineBuilder:
    def __init__(self, max_chars: int = 100, max_seconds: float = 12.0):
        self.max_chars = max_chars
        self.max_seconds = max_seconds
        self._next_id = 0
        self._open: list[Word] = []
        self._open_sent = False  # a partial for the current id has been sent to the client

    def update(self, committed: list[Word], tentative: list[Word]) -> list[Update]:
        out: list[Update] = []
        for w in committed:
            self._open.append(w)
            if self._should_close():
                out.append(self._close())
        if self._open or tentative:
            words = self._open + list(tentative)
            out.append(Update(self._next_id, words[0].start, words[-1].end, join_words(words), False))
            self._open_sent = True
        elif self._open_sent:
            out.append(Update(self._next_id, 0.0, 0.0, "", False))  # retract a stale partial
            self._open_sent = False
        return out

    def finish(self, committed: list[Word]) -> list[Update]:
        """End of stream (or seek): everything becomes final; no partial is left behind."""
        out: list[Update] = []
        for w in committed:
            self._open.append(w)
            if self._should_close():
                out.append(self._close())
        if self._open:
            out.append(self._close())
        elif self._open_sent:
            out.append(Update(self._next_id, 0.0, 0.0, "", False))
            self._open_sent = False
        return out

    def _should_close(self) -> bool:
        text = join_words(self._open)
        if text and text[-1] in SENTENCE_END:
            return True
        if len(text) >= self.max_chars:
            return True
        return bool(self._open) and (self._open[-1].end - self._open[0].start) >= self.max_seconds

    def _close(self) -> Update:
        words = self._open
        update = Update(self._next_id, words[0].start, words[-1].end, join_words(words), True)
        self._next_id += 1
        self._open = []
        self._open_sent = False
        return update
