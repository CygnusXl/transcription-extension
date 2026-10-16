"""Pre-download the models so the first live session does not stall.

    python -m backend.download_models            # ASR + translation
    python -m backend.download_models --asr-only
"""
from __future__ import annotations

import argparse

from . import config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asr-only", action="store_true")
    parser.add_argument("--translation-only", action="store_true")
    args = parser.parse_args()

    if not args.translation_only:
        from .streaming_asr import FasterWhisperTranscriber

        print(f"Downloading ASR model {config.ASR_MODEL!r} ...")
        FasterWhisperTranscriber(config.ASR_MODEL, "cpu", "int8", download_root=str(config.MODELS_DIR / "whisper"))
    if not args.asr_only:
        from .translator import Translator

        print(f"Downloading translation model {config.TRANSLATION_MODEL!r} (about 2.4 GB) ...")
        Translator(config.TRANSLATION_MODEL, "cpu", cache_dir=str(config.MODELS_DIR / "hf"))
    print("Done. Models are stored under", config.MODELS_DIR)


if __name__ == "__main__":
    main()
