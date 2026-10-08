"""Local translation (Stage 5 - not implemented yet).

Candidates: NLLB-200 distilled or M2M100 via Hugging Face, run locally.
Translation must preserve each segment's start/end timestamps.
"""
from __future__ import annotations


class Translator:
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        raise NotImplementedError("Stage 5")
