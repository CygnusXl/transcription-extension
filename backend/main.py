"""Local backend: FastAPI + WebSocket.

    uvicorn backend.main:app --host 127.0.0.1 --port 8765

Only bind to localhost. Browser pages other than this extension are refused on /ws, so a random
website cannot use your GPU through the socket.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .models import Models
from .session import Session

logging.basicConfig(level=logging.INFO)


def create_app(models: Models | None = None) -> FastAPI:
    models = models or Models()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        database.init_db()
        yield

    app = FastAPI(title="Transcription Extension Backend", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "time": time.time(), **models.info()}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        origin = ws.headers.get("origin")
        if origin and not origin.startswith("chrome-extension://"):
            await ws.close(code=1008)  # policy violation: only the extension may connect
            return
        await Session(ws, models).run()

    return app


app = create_app()
