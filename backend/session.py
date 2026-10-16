"""One WebSocket session = one live transcription of one browser tab.

Client -> server
    text   {"type":"hello","videoId":..,"sourceLang":"auto|xx","targetLang":"xx|''"}
    text   {"type":"settings","sourceLang":..,"targetLang":..}
    text   {"type":"sync","t":<video seconds>,"playing":bool,"rate":float}   (playback position)
    text   {"type":"video","videoId":..}                                      (tab moved to another video)
    text   {"type":"stop"}
    binary little-endian int16 mono 16 kHz PCM

Server -> client
    {"type":"ack"} | {"type":"status","state":..,"detail":..}
    {"type":"transcript","id","start","end","text","final","lang","latencyMs","stableLatencyMs"}
    {"type":"translation","id","text","translation","target"}
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect

from . import config, database, language
from .latency import ArrivalClock
from .streaming_asr import StepResult, StreamingASR
from .transcript import LineBuilder, Update

log = logging.getLogger("session")


@dataclass
class _Pending:
    id: int
    text: str
    final: bool
    start_ms: int
    src: str | None


class Session:
    def __init__(self, ws: WebSocket, models):
        self.ws = ws
        self.models = models
        self.video_id = "unknown"
        self.source: str | None = None
        self.target: str | None = None

        self._tx = None  # set once the model is loaded
        self.asr = StreamingASR(
            lambda audio, lang, prompt, offset: self._tx(audio, lang, prompt, offset),
            step_seconds=config.ASR_STEP_SECONDS,
            max_buffer_seconds=config.ASR_MAX_BUFFER_SECONDS,
        )
        self.lines = LineBuilder()
        self.clock = ArrivalClock()

        self._send_lock = asyncio.Lock()
        self._asr_lock = asyncio.Lock()
        self._audio_event = asyncio.Event()
        self._tr_event = asyncio.Event()
        self._pending: dict[int, _Pending] = {}
        self._last_tr: dict[int, tuple[float, str]] = {}
        self._recent_finals: list[_Pending] = []
        self._tr_disabled = False

        self._paused = False
        self._anchor: tuple[float, float, float] | None = None  # (audio_clock_s, video_s, rate)

    # ---- plumbing ---------------------------------------------------------
    async def _send(self, msg: dict) -> None:
        async with self._send_lock:
            try:
                await self.ws.send_json(msg)
            except Exception:  # client went away
                pass

    async def _status(self, state: str, detail: str | None = None) -> None:
        await self._send({"type": "status", "state": state, "detail": detail})

    def _vt(self, audio_t: float) -> float:
        """Audio-clock seconds -> video-timeline seconds."""
        if self._anchor is None:
            return audio_t
        a, v, rate = self._anchor
        return v + (audio_t - a) * rate

    # ---- main loop --------------------------------------------------------
    async def run(self) -> None:
        await self.ws.accept()
        tasks = [asyncio.create_task(self._asr_loop()), asyncio.create_task(self._translation_loop())]
        try:
            while True:
                msg = await self.ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    self._on_audio(msg["bytes"])
                elif msg.get("text") is not None:
                    try:
                        await self._on_text(json.loads(msg["text"]))
                    except (ValueError, TypeError) as exc:
                        await self._send({"type": "status", "state": "error", "detail": f"bad message: {exc}"})
        except WebSocketDisconnect:
            pass
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await asyncio.to_thread(database.set_status, self.video_id, "stopped", self.asr.language_in_use)
            except Exception:
                log.exception("could not update video status")

    def _on_audio(self, data: bytes) -> None:
        if self._paused:
            return  # video paused: tab audio is silence and must not advance the audio clock
        if len(data) % 2:
            data = data[:-1]
        self.asr.feed(data)
        self.clock.record(self.asr.fed_samples)
        self._audio_event.set()

    async def _on_text(self, data: dict) -> None:
        kind = data.get("type")
        if kind == "hello":
            self.video_id = str(data.get("videoId") or "unknown")
            self.source = language.normalize_source(data.get("sourceLang"))
            self.target = language.normalize_target(data.get("targetLang"))
            self.asr.set_language(self.source)
            try:
                await asyncio.to_thread(database.init_db)
                await asyncio.to_thread(database.set_status, self.video_id, "live", self.source)
            except Exception:
                log.exception("database unavailable; continuing without cache")
            await self._send({"type": "ack", "videoId": self.video_id})
        elif kind == "settings":
            await self._on_settings(data)
        elif kind == "sync":
            await self._on_sync(data)
        elif kind == "video":
            await self._restart(video_id=str(data.get("videoId") or "unknown"))
        elif kind == "stop":
            await self._finish_and_reset()
            await self._status("stopped")

    async def _on_settings(self, data: dict) -> None:
        src = language.normalize_source(data.get("sourceLang"))
        tgt = language.normalize_target(data.get("targetLang"))
        if src != self.source:
            self.source = src
            self.asr.set_language(src)
        if tgt != self.target:
            self.target = tgt
            self._pending.clear()
            if tgt:  # re-translate what is already on screen
                for item in self._recent_finals:
                    self._pending[item.id] = item
                self._tr_event.set()

    async def _on_sync(self, data: dict) -> None:
        t = float(data.get("t", 0.0))
        playing = bool(data.get("playing"))
        rate = float(data.get("rate") or 1.0)
        clock = self.asr.fed_seconds
        if not playing:
            self._paused = True
            return
        self._paused = False
        if self._anchor is None:
            self._anchor = (clock, t, rate)
            return
        if abs(self._vt(clock) - t) > 1.0:  # the viewer seeked
            await self._finish_and_reset()
            self._anchor = (self.asr.fed_seconds, t, rate)
        elif abs(rate - self._anchor[2]) > 1e-6:
            self._anchor = (clock, t, rate)

    async def _restart(self, video_id: str) -> None:
        await self._finish_and_reset()
        self.video_id = video_id
        self._anchor = None
        self._recent_finals.clear()
        self._pending.clear()
        try:
            await asyncio.to_thread(database.set_status, video_id, "live", self.source)
        except Exception:
            log.exception("could not update video status")

    # ---- ASR --------------------------------------------------------------
    async def _asr_loop(self) -> None:
        try:
            await self._status("loading_model", self.models.info().get("asr_configured"))
            self._tx = await asyncio.to_thread(self.models.get_transcriber)
        except Exception as exc:
            log.exception("ASR model failed to load")
            await self._status("error", f"ASR model failed to load: {exc}")
            return
        async with self._asr_lock:
            self.asr.keep_recent(10.0)  # audio that piled up while the model was loading
        info = self.models.info()
        await self._status("listening", f"{info.get('asr_model')} on {info.get('asr_device')}")
        while True:
            await self._audio_event.wait()
            self._audio_event.clear()
            while not self._paused and self.asr.ready():
                async with self._asr_lock:
                    res = await asyncio.to_thread(self.asr.step)
                await self._emit(res)

    async def _finish_and_reset(self) -> None:
        if self._tx is None:
            self.asr.reset()
            return
        async with self._asr_lock:
            res = await asyncio.to_thread(self.asr.finish)
            updates = self.lines.finish(res.committed)
            for u in updates:
                await self._publish(u, res, latency=None)
            self.asr.reset()

    async def _emit(self, res: StepResult) -> None:
        updates = self.lines.update(res.committed, res.tentative)
        now = time.monotonic()
        newest = res.tentative or res.committed
        latency = self._latency_ms(newest[-1].end, now) if newest else None
        stable = self._latency_ms(res.committed[-1].end, now) if res.committed else None
        for u in updates:
            await self._publish(u, res, latency, stable)

    def _latency_ms(self, audio_t: float, now: float) -> int | None:
        captured = self.clock.capture_time(audio_t)
        return None if captured is None else max(0, int((now - captured) * 1000))

    async def _publish(self, u: Update, res: StepResult, latency, stable=None) -> None:
        await self._send(
            {
                "type": "transcript",
                "id": u.id,
                "start": round(self._vt(u.start), 2),
                "end": round(self._vt(u.end), 2),
                "text": u.text,
                "final": u.final,
                "lang": res.language,
                "latencyMs": latency,
                "stableLatencyMs": stable,
            }
        )
        if not u.text:
            return
        item = _Pending(u.id, u.text, u.final, int(round(self._vt(u.start) * 1000)), res.language)
        if u.final:
            self._recent_finals = (self._recent_finals + [item])[-30:]
            try:
                await asyncio.to_thread(
                    database.save_segment,
                    self.video_id, item.start_ms, int(round(self._vt(u.end) * 1000)), res.language, u.text,
                )
            except Exception:
                log.exception("could not cache segment")
        self._queue_translation(item)

    # ---- translation ------------------------------------------------------
    def _queue_translation(self, item: _Pending) -> None:
        if not self.target or self._tr_disabled or not item.src or item.src == self.target:
            return
        if not item.final:  # throttle partials: at most one translation per ~1.2 s per line
            last_time, last_text = self._last_tr.get(item.id, (0.0, ""))
            if last_text == item.text or time.monotonic() - last_time < 1.2:
                return
        self._last_tr[item.id] = (time.monotonic(), item.text)
        self._pending[item.id] = item
        self._tr_event.set()

    async def _translation_loop(self) -> None:
        translator = None
        while True:
            await self._tr_event.wait()
            self._tr_event.clear()
            items = sorted(self._pending.values(), key=lambda p: (not p.final, p.id))
            self._pending.clear()
            for it in items:
                target = self.target
                if not target or not it.src or it.src == target or self._tr_disabled:
                    continue
                try:
                    if translator is None:
                        await self._status("loading_translation", self.models.info().get("translation_configured"))
                        translator = await asyncio.to_thread(self.models.get_translator)
                        await self._status("listening")
                    translated = await asyncio.to_thread(translator.translate, it.text, it.src, target)
                except Exception as exc:
                    log.exception("translation failed")
                    self._tr_disabled = True
                    await self._status("translation_unavailable", str(exc))
                    break
                if target != self.target:
                    continue  # target language changed while translating
                await self._send(
                    {"type": "translation", "id": it.id, "text": it.text, "translation": translated, "target": target}
                )
                if it.final:
                    try:
                        await asyncio.to_thread(database.save_translation, self.video_id, it.start_ms, target, translated)
                    except Exception:
                        log.exception("could not cache translation")
