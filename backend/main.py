"""Local backend: FastAPI + WebSocket.

Stage 2: health endpoint and a WebSocket that accepts the extension's hello message
and binary PCM frames. Stage 3 will route audio into streaming_asr.StreamingASR.
"""
from __future__ import annotations

import json
import logging
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db

log = logging.getLogger("backend")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Transcription Extension Backend")

# The extension talks to localhost only; allow its origin for HTTP health checks.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    # asr_model is None until Stage 3 loads a model.
    return {"status": "ok", "asr_model": None, "time": time.time()}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session: dict = {}
    bytes_received = 0
    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text") is not None:
                data = json.loads(message["text"])
                if data.get("type") == "hello":
                    session = data
                    log.info("session started: %s", session)
                    await ws.send_json({"type": "ack", "videoId": data.get("videoId")})
            elif message.get("bytes") is not None:
                # Stage 3: feed PCM16 16 kHz mono frames to the streaming ASR.
                bytes_received += len(message["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        log.info("session ended (%s bytes of audio received)", bytes_received)
