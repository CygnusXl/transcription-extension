"""Local machine translation with NLLB-200 (distilled 600M) via Hugging Face transformers.

Runs entirely on this machine. Translation never changes the segment timestamps: the caller keeps
the ASR start/end and only attaches the translated text.
"""
from __future__ import annotations

import threading

from .language import nllb_code


class Translator:
    def __init__(self, model_name: str, device: str = "auto", cache_dir: str | None = None):
        import torch  # imported lazily: heavy, optional for tests
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.name = model_name
        self.device = device
        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        dtype = torch.float16 if device == "cuda" else torch.float32
        try:  # transformers >= 4.56 / 5.x renamed torch_dtype -> dtype
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name, cache_dir=cache_dir, dtype=dtype)
        except TypeError:
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name, cache_dir=cache_dir, torch_dtype=dtype)
        self._model = model.to(device).eval()
        self._lock = threading.Lock()

    def translate(self, text: str, src: str, tgt: str) -> str:
        text = text.strip()
        if not text or src == tgt:
            return text
        src_code, tgt_code = nllb_code(src), nllb_code(tgt)
        if src_code is None or tgt_code is None:
            raise ValueError(f"unsupported language pair {src!r} -> {tgt!r}")
        torch = self._torch
        with self._lock, torch.inference_mode():
            self._tok.src_lang = src_code
            enc = self._tok(text, return_tensors="pt", truncation=True, max_length=256).to(self.device)
            out = self._model.generate(
                **enc,
                forced_bos_token_id=self._tok.convert_tokens_to_ids(tgt_code),
                max_new_tokens=int(enc["input_ids"].shape[1] * 2 + 10),
                num_beams=2,
            )
            return self._tok.batch_decode(out, skip_special_tokens=True)[0]
