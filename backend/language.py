"""Language helpers: normalisation of user choices and mapping to NLLB codes."""
from __future__ import annotations

# Languages offered in the extension popup.
UI_LANGUAGES = ["en", "id", "ja", "ko", "zh", "es", "de"]

# Whisper language code -> NLLB-200 code. The first seven are the UI languages; the rest cover
# other languages Whisper may detect so that translation still works for them.
NLLB_CODES = {
    "en": "eng_Latn",
    "id": "ind_Latn",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "zh": "zho_Hans",
    "es": "spa_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "pt": "por_Latn",
    "ru": "rus_Cyrl",
    "ar": "arb_Arab",
    "hi": "hin_Deva",
    "th": "tha_Thai",
    "vi": "vie_Latn",
    "it": "ita_Latn",
    "tr": "tur_Latn",
    "nl": "nld_Latn",
    "pl": "pol_Latn",
    "ms": "zsm_Latn",
}


def normalize_source(lang: str | None) -> str | None:
    """None means auto-detect."""
    if not lang or lang == "auto":
        return None
    return lang.lower()


def normalize_target(lang: str | None) -> str | None:
    """None means translation is off (or the language is not translatable)."""
    if not lang:
        return None
    lang = lang.lower()
    return lang if lang in NLLB_CODES else None


def nllb_code(lang: str) -> str | None:
    return NLLB_CODES.get(lang)
