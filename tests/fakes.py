"""Test doubles: a scripted 'speaker' and a fake transcriber that behaves like a streaming Whisper.

The fake returns, for any audio window, the scripted words that lie fully inside the window.
Words that ended less than ``unstable`` seconds before the window end are returned *wrong*,
imitating Whisper's tendency to revise the tail of a hypothesis once more audio arrives.
"""
from __future__ import annotations

from backend.streaming_asr import SAMPLE_RATE, Word

SCRIPT = [
    ("Today", 0.0, 0.4),
    (" we", 0.4, 0.6),
    (" are", 0.6, 0.8),
    (" going", 0.8, 1.1),
    (" to", 1.1, 1.2),
    (" discuss", 1.2, 1.7),
    (" convolutional", 1.7, 2.5),
    (" neural", 2.5, 2.9),
    (" networks.", 2.9, 3.5),
]
SCRIPT_TEXT = "Today we are going to discuss convolutional neural networks."


def make_fake_transcriber(script=SCRIPT, unstable: float = 0.6, language: str = "en", calls: list | None = None):
    def transcribe(audio, lang, prompt, offset):
        end = offset + len(audio) / SAMPLE_RATE
        words = []
        for text, s, e in script:
            if s >= offset - 1e-9 and e <= end + 1e-9:
                shown = " wrongword" if end - e < unstable else text
                words.append(Word(s - offset, e - offset, shown))
        if calls is not None:
            calls.append((offset, len(audio) / SAMPLE_RATE, lang, prompt))
        return words, language, 0.99

    transcribe.name = "fake"
    transcribe.device = "cpu"
    return transcribe


class FakeTranslator:
    def translate(self, text, src, tgt):
        return f"[{src}->{tgt}] {text}"


def pcm_silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(seconds * SAMPLE_RATE)
