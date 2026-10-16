"""Latency and real-time-factor helpers.

latency = time a transcript is shown - time the corresponding speech was captured
RTF     = processing time / audio duration  (RTF < 1 means faster than real time)
"""
from __future__ import annotations

import statistics
import threading
import time
from bisect import bisect_left

SAMPLE_RATE = 16_000


def rtf(processing_seconds: float, audio_seconds: float) -> float:
    return processing_seconds / audio_seconds


def summarize(latencies_ms: list[float]) -> dict:
    if not latencies_ms:
        return {}
    return {
        "n": len(latencies_ms),
        "mean": statistics.fmean(latencies_ms),
        "median": statistics.median(latencies_ms),
        "min": min(latencies_ms),
        "max": max(latencies_ms),
        "std": statistics.stdev(latencies_ms) if len(latencies_ms) > 1 else 0.0,
    }


class ArrivalClock:
    """Maps a position on the audio clock to the wall-clock time at which it was captured.

    The audio clock counts seconds of audio fed so far. Audio arrives in real time in small
    chunks, so a sample's capture time is approximated as the chunk's arrival time minus the
    time between that sample and the end of the chunk. Measured latency therefore does not include
    delay that happens before the audio reaches the backend (tab capture, audio worklet buffering).
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, keep_seconds: float = 90.0):
        self._sr = sample_rate
        self._keep = keep_seconds
        self._ends: list[int] = []  # cumulative samples at the end of each chunk
        self._times: list[float] = []  # wall-clock arrival time of each chunk
        self._lock = threading.Lock()

    def record(self, total_samples: int, wall_time: float | None = None) -> None:
        now = time.monotonic() if wall_time is None else wall_time
        with self._lock:
            self._ends.append(total_samples)
            self._times.append(now)
            while len(self._ends) > 1 and (self._ends[-1] - self._ends[0]) / self._sr > self._keep:
                self._ends.pop(0)
                self._times.pop(0)

    def capture_time(self, audio_seconds: float) -> float | None:
        idx = int(audio_seconds * self._sr)
        with self._lock:
            if not self._ends:
                return None
            k = min(bisect_left(self._ends, idx), len(self._ends) - 1)
            return self._times[k] - (self._ends[k] - idx) / self._sr
