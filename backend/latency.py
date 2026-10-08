"""Latency and real-time-factor helpers.

latency = time transcript is emitted - time the corresponding speech occurred
RTF     = processing time / audio duration  (RTF < 1 means faster than real time)
"""
from __future__ import annotations

import statistics


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
