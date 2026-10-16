"""Lazy, shared model registry. Models load on first use and are shared by all sessions."""
from __future__ import annotations

import threading
from typing import Any, Callable

from . import config


def _cuda_available_ct2() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _default_transcriber():
    from .streaming_asr import FasterWhisperTranscriber

    device = config.ASR_DEVICE
    if device == "auto":
        device = "cuda" if _cuda_available_ct2() else "cpu"
    compute = config.ASR_COMPUTE
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return FasterWhisperTranscriber(
        config.ASR_MODEL, device, compute, download_root=str(config.MODELS_DIR / "whisper")
    )


def _default_translator():
    from .translator import Translator

    return Translator(
        config.TRANSLATION_MODEL, config.TRANSLATION_DEVICE, cache_dir=str(config.MODELS_DIR / "hf")
    )


class Models:
    def __init__(
        self,
        transcriber_factory: Callable[[], Any] | None = None,
        translator_factory: Callable[[], Any] | None = None,
    ):
        self._transcriber_factory = transcriber_factory or _default_transcriber
        self._translator_factory = translator_factory or _default_translator
        self._asr: Any = None
        self._translator: Any = None
        self._lock = threading.Lock()

    def get_transcriber(self):
        with self._lock:
            if self._asr is None:
                self._asr = self._transcriber_factory()
            return self._asr

    def get_translator(self):
        with self._lock:
            if self._translator is None:
                self._translator = self._translator_factory()
            return self._translator

    def info(self) -> dict:
        return {
            "asr_model": getattr(self._asr, "name", None) if self._asr else None,
            "asr_device": getattr(self._asr, "device", None) if self._asr else None,
            "asr_configured": config.ASR_MODEL,
            "translation_loaded": self._translator is not None,
            "translation_configured": config.TRANSLATION_MODEL,
        }
