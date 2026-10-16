"""Streaming ASR on top of a non-streaming model (Whisper), using LocalAgreement-2.

Whisper is not a streaming model, so streaming is emulated:

1. Audio is appended to a buffer as it arrives.
2. Every ``step_seconds`` of new audio the whole buffer is re-transcribed (with word timestamps).
3. Words that appear in the same position in two consecutive hypotheses are *committed*
   (stable, shown as final). The remaining words of the newest hypothesis are *tentative*
   (shown as partial text and allowed to change).
4. Once words are committed, the buffer is trimmed so the window stays short and inference stays fast.

The approach follows Machacek, Dabre and Bojar, "Turning Whisper into Real-Time Transcription
System" (2023). This is an independent implementation; the transcriber is injected, so the
algorithm can be tested without a model.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class Word:
    start: float  # seconds on the audio clock
    end: float
    text: str  # may carry a leading space (Latin scripts); join with ""


def join_words(words: list[Word]) -> str:
    return "".join(w.text for w in words).strip()


def _key(w: Word) -> str:
    """Comparison key: ignores case and punctuation; falls back to raw text for pure punctuation."""
    return re.sub(r"[\W_]+", "", w.text.lower()) or w.text.strip()


# transcribe(audio_float32_16k, language_or_None, prompt_or_None, buffer_offset_seconds)
#   -> (words relative to the start of `audio`, detected_language, language_probability)
Transcriber = Callable[[np.ndarray, "str | None", "str | None", float], "tuple[list[Word], str | None, float]"]


@dataclass
class StepResult:
    committed: list[Word]
    tentative: list[Word]
    language: str | None
    audio_end: float  # audio-clock position of the newest audio included in this step
    infer_seconds: float = 0.0


class LocalAgreement:
    """Commits the longest common prefix of two consecutive hypotheses."""

    def __init__(self, committed_end: float = 0.0):
        self.committed_end = committed_end
        self.tail: list[Word] = []  # last committed words, used to remove overlap
        self.prev: list[Word] = []  # unconfirmed words of the previous hypothesis

    def _drop_committed(self, hyp: list[Word]) -> list[Word]:
        # A word already committed if its midpoint lies before the committed boundary.
        hyp = [w for w in hyp if (w.start + w.end) / 2 > self.committed_end]
        # Timestamps can shift slightly between runs; also remove a repeated committed tail by text.
        tail = self.tail[-5:]
        for k in range(min(len(tail), len(hyp), 5), 0, -1):
            if [_key(w) for w in hyp[:k]] == [_key(w) for w in tail[-k:]] and hyp[0].start < self.committed_end + 1.0:
                return hyp[k:]
        return hyp

    def update(self, hyp: list[Word]) -> tuple[list[Word], list[Word]]:
        """Returns (newly committed words, tentative words)."""
        hyp = self._drop_committed(hyp)
        n = 0
        while n < len(hyp) and n < len(self.prev) and _key(hyp[n]) == _key(self.prev[n]):
            n += 1
        committed, tentative = hyp[:n], hyp[n:]
        if committed:
            self.commit(committed)
        self.prev = tentative
        return committed, tentative

    def commit(self, words: list[Word]) -> None:
        self.tail = (self.tail + list(words))[-8:]
        self.committed_end = max(self.committed_end, words[-1].end)


class StreamingASR:
    def __init__(
        self,
        transcribe: Transcriber,
        *,
        step_seconds: float = 1.0,
        min_seconds: float = 1.0,
        max_buffer_seconds: float = 15.0,
        language: str | None = None,
        lock_probability: float = 0.7,
        prompt_chars: int = 200,
    ):
        self._tx = transcribe
        self.step_seconds = step_seconds
        self.min_seconds = min_seconds
        self.max_buffer_seconds = max_buffer_seconds
        self.language = language  # user-selected; None = auto-detect
        self.lock_probability = lock_probability
        self.prompt_chars = prompt_chars

        self._lock = threading.Lock()
        self._chunks: list[np.ndarray] = []
        self._buf = np.zeros(0, dtype=np.float32)
        self.buffer_start = 0.0  # audio-clock time of _buf[0]
        self.fed_samples = 0
        self._last_step_fed = 0

        self.agreement = LocalAgreement()
        self.locked_language: str | None = None
        self.last_detected: str | None = None
        self._history: list[Word] = []  # recent committed words, used to build the context prompt

    # ---- audio in ---------------------------------------------------------
    @property
    def fed_seconds(self) -> float:
        return self.fed_samples / SAMPLE_RATE

    def feed(self, pcm16: bytes) -> None:
        """Append little-endian signed 16-bit mono 16 kHz PCM."""
        arr = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
        with self._lock:
            self._chunks.append(arr)
            self.fed_samples += len(arr)

    def ready(self) -> bool:
        with self._lock:
            new = (self.fed_samples - self._last_step_fed) / SAMPLE_RATE
            buffered = (self.fed_samples - int(round(self.buffer_start * SAMPLE_RATE))) / SAMPLE_RATE
        return new >= self.step_seconds and buffered >= self.min_seconds

    def set_language(self, language: str | None) -> None:
        self.language = language
        self.locked_language = None

    @property
    def language_in_use(self) -> str | None:
        return self.language or self.locked_language or self.last_detected

    # ---- inference --------------------------------------------------------
    def step(self, force: bool = False) -> StepResult:
        with self._lock:
            self._merge_chunks()
            audio = self._buf.copy()
            offset = self.buffer_start
            fed = self.fed_samples
            self._last_step_fed = fed
        audio_end = fed / SAMPLE_RATE
        if len(audio) / SAMPLE_RATE < (0.3 if force else self.min_seconds):
            return StepResult([], list(self.agreement.prev), self.language_in_use, audio_end)

        started = time.perf_counter()
        rel, detected, prob = self._tx(audio, self.language or self.locked_language, self._context_prompt(offset), offset)
        infer = time.perf_counter() - started

        words = [Word(w.start + offset, w.end + offset, w.text) for w in rel]
        self._update_language(detected, prob, words)

        if not words:
            self.agreement.prev = []
            if audio_end - self.buffer_start > 4.0:  # long stretch with no speech: drop it
                self._trim_to(audio_end - 1.0)
                self.agreement.committed_end = max(self.agreement.committed_end, self.buffer_start)
            return StepResult([], [], self.language_in_use, audio_end, infer)

        committed, tentative = self.agreement.update(words)
        extra, tentative = self._maybe_trim(audio_end, tentative)
        committed = committed + extra
        if committed:
            self._history = (self._history + committed)[-80:]
        return StepResult(committed, tentative, self.language_in_use, audio_end, infer)

    def finish(self) -> StepResult:
        """Run a last pass and commit everything still tentative (end of stream)."""
        res = self.step(force=True)
        tail = list(self.agreement.prev)
        self.agreement.prev = []
        return StepResult(res.committed + tail, [], res.language, res.audio_end, res.infer_seconds)

    def reset(self) -> None:
        """Drop buffered audio and hypotheses (seek / new video). The audio clock keeps running."""
        with self._lock:
            self._chunks.clear()
            self._buf = np.zeros(0, dtype=np.float32)
            self.buffer_start = self.fed_samples / SAMPLE_RATE
            self._last_step_fed = self.fed_samples
        self.agreement = LocalAgreement(committed_end=self.buffer_start)
        self._history = []

    def _context_prompt(self, offset: float) -> str | None:
        """Text that precedes the audio window, to help Whisper with names and style.

        Only words that already scrolled *out* of the window may be used. Passing text that is
        still inside the window makes Whisper believe it was already transcribed and it may then
        output nothing for that audio.
        """
        before = [w for w in self._history if w.end <= offset + 0.05]
        text = join_words(before)[-self.prompt_chars :].strip()
        return text or None

    def keep_recent(self, seconds: float) -> None:
        """Discard audio older than ``seconds`` (used after a slow model load)."""
        with self._lock:
            self._merge_chunks()
            target = self.fed_samples / SAMPLE_RATE - seconds
            if target > self.buffer_start:
                self._trim_locked(target)
        self.agreement.committed_end = max(self.agreement.committed_end, self.buffer_start)

    # ---- internals --------------------------------------------------------
    def _merge_chunks(self) -> None:
        if self._chunks:
            self._buf = np.concatenate([self._buf, *self._chunks])
            self._chunks.clear()

    def _trim_locked(self, abs_time: float) -> None:
        n = int(round((abs_time - self.buffer_start) * SAMPLE_RATE))
        n = max(0, min(n, len(self._buf)))
        self._buf = self._buf[n:]
        self.buffer_start += n / SAMPLE_RATE

    def _trim_to(self, abs_time: float) -> None:
        with self._lock:
            self._merge_chunks()
            self._trim_locked(abs_time)

    def _update_language(self, detected: str | None, prob: float, words: list[Word]) -> None:
        if detected:
            self.last_detected = detected
        if self.language is None and self.locked_language is None and detected:
            speech = sum(w.end - w.start for w in words)
            if prob >= self.lock_probability and speech >= 2.0:
                self.locked_language = detected  # stop re-detecting every step

    def _maybe_trim(self, audio_end: float, tentative: list[Word]) -> tuple[list[Word], list[Word]]:
        """Keep the window short. Returns (words force-committed by trimming, remaining tentative)."""
        committed_end = self.agreement.committed_end
        if audio_end - self.buffer_start > self.max_buffer_seconds:
            if committed_end > self.buffer_start + 1.0:
                self._trim_to(committed_end)
                return [], tentative
            # Hypotheses never stabilised: commit what we have up to the cut so text is not lost.
            cut = audio_end - self.max_buffer_seconds * 0.66
            forced = [w for w in tentative if (w.start + w.end) / 2 <= cut]
            rest = tentative[len(forced) :]
            if forced:
                self.agreement.commit(forced)
            self.agreement.committed_end = max(self.agreement.committed_end, cut)
            self.agreement.prev = rest
            self._trim_to(cut)
            return forced, rest
        if not tentative and committed_end < audio_end - 2.0:  # everything stable, trailing silence
            self._trim_to(max(committed_end, audio_end - 1.0))
        return [], tentative


class FasterWhisperTranscriber:
    """Transcriber backed by faster-whisper (CTranslate2). Local inference only."""

    def __init__(self, model: str, device: str, compute_type: str, download_root: str | None = None):
        from faster_whisper import WhisperModel  # imported lazily: heavy, optional for tests

        self.name = model
        self.device = device
        self.compute_type = compute_type
        self._model = WhisperModel(model, device=device, compute_type=compute_type, download_root=download_root)
        self._lock = threading.Lock()  # one inference at a time per model

    def __call__(self, audio, language, prompt, offset=0.0):
        with self._lock:
            segments, info = self._model.transcribe(
                audio,
                language=language,
                task="transcribe",
                beam_size=1,  # greedy decoding: lowest latency
                temperature=0.0,
                condition_on_previous_text=False,
                initial_prompt=prompt,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
            )
            words: list[Word] = []
            for seg in segments:  # generator: must be consumed while the lock is held
                if seg.no_speech_prob is not None and seg.no_speech_prob > 0.8 and seg.avg_logprob < -1.0:
                    continue  # likely hallucination on non-speech
                for w in seg.words or []:
                    words.append(Word(float(w.start), float(w.end), w.word))
        return words, info.language, float(info.language_probability)
