"""Runtime configuration, read from environment variables (all optional)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


# --- ASR -------------------------------------------------------------------
ASR_MODEL = os.environ.get("TXE_ASR_MODEL", "small")  # tiny | base | small | medium | large-v3-turbo | ...
ASR_DEVICE = os.environ.get("TXE_ASR_DEVICE", "auto")  # auto | cuda | cpu
ASR_COMPUTE = os.environ.get("TXE_ASR_COMPUTE", "auto")  # auto | float16 | int8_float16 | int8
ASR_STEP_SECONDS = _float("TXE_STEP_SECONDS", 1.0)  # run inference after this much new audio
ASR_MAX_BUFFER_SECONDS = _float("TXE_MAX_BUFFER_SECONDS", 15.0)  # sliding window upper bound

# --- Translation -----------------------------------------------------------
TRANSLATION_MODEL = os.environ.get("TXE_TRANSLATION_MODEL", "facebook/nllb-200-distilled-600M")
TRANSLATION_DEVICE = os.environ.get("TXE_TRANSLATION_DEVICE", "auto")  # auto | cuda | cpu

# --- Storage ---------------------------------------------------------------
MODELS_DIR = Path(os.environ.get("TXE_MODELS_DIR", ROOT / "models"))
DB_PATH = Path(os.environ.get("TXE_DB", ROOT / "data" / "cache.sqlite3"))
