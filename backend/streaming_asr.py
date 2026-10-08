"""Streaming ASR (Stage 3 - not implemented yet).

Plan: faster-whisper on GPU with a sliding audio buffer. Every ~0.5-1 s, transcribe the
unconfirmed window, compare with the previous hypothesis (local agreement), emit the
stable prefix as final and the rest as partial.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass
class Segment:
    id: int
    start: float
    end: float
    text: str
    final: bool
    language: str | None = None


class StreamingASR:
    SAMPLE_RATE = 16_000

    def __init__(self, model_size: str = "small", device: str = "cuda", compute_type: str = "float16"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        # TODO(Stage 3): load faster_whisper.WhisperModel here.

    def accept_audio(self, pcm16: bytes) -> Iterator[Segment]:
        """Feed PCM16 mono 16 kHz bytes; yield partial/final segments."""
        raise NotImplementedError("Stage 3")
        yield  # pragma: no cover
