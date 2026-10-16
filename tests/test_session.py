"""End-to-end test of the WebSocket protocol with a scripted fake model (no GPU, no browser)."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import create_app
from backend.models import Models

from .fakes import SCRIPT_TEXT, FakeTranslator, make_fake_transcriber, pcm_silence


def collect(ws, inbox, done):
    try:
        while True:
            msg = ws.receive_json()
            inbox.append(msg)
            if msg.get("type") == "status" and msg.get("state") == "stopped":
                break
    except Exception:  # connection closed
        pass
    finally:
        done.set()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "cache.sqlite3")
    models = Models(lambda: make_fake_transcriber(), lambda: FakeTranslator())
    with TestClient(create_app(models)) as c:
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["asr_configured"]


def test_foreign_origin_is_refused(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}):
            pass


def test_live_transcript_partials_then_finals_with_translation_and_cache(client):
    inbox, done = [], threading.Event()
    with client.websocket_connect("/ws", headers={"origin": "chrome-extension://abc"}) as ws:
        threading.Thread(target=collect, args=(ws, inbox, done), daemon=True).start()
        ws.send_json({"type": "hello", "videoId": "vid1", "sourceLang": "auto", "targetLang": "id"})
        ws.send_json({"type": "sync", "t": 100.0, "playing": True, "rate": 1.0})
        for _ in range(7):  # 7 s of audio in 100 ms frames, a second at a time
            for _ in range(10):
                ws.send_bytes(pcm_silence(0.1))
            time.sleep(0.4)
        ws.send_json({"type": "stop"})
        assert done.wait(10), "session did not finish"

    transcripts = [m for m in inbox if m["type"] == "transcript"]
    finals = [m for m in transcripts if m["final"]]
    partials = [m for m in transcripts if not m["final"] and m["text"]]

    # Genuinely live: partial text was delivered, and before the first final line.
    assert partials
    assert transcripts.index(partials[0]) < transcripts.index(finals[0])
    assert [m["text"] for m in finals] == [SCRIPT_TEXT]

    # Timestamps are on the video timeline (anchored at t=100 s by the first sync message).
    assert abs(finals[0]["start"] - 100.0) < 0.05 and abs(finals[0]["end"] - 103.5) < 0.05
    assert finals[0]["lang"] == "en" and finals[0]["latencyMs"] is None or finals[0]["latencyMs"] >= 0

    translations = [m for m in inbox if m["type"] == "translation" and m["id"] == finals[0]["id"]]
    assert translations and translations[-1]["translation"] == f"[en->id] {SCRIPT_TEXT}"

    rows = database.load_segments("vid1", "id")
    assert [r["text"] for r in rows] == [SCRIPT_TEXT]
    assert rows[0]["start_ms"] == 100_000 and rows[0]["translation"] == f"[en->id] {SCRIPT_TEXT}"


def test_paused_video_does_not_advance_the_timeline(client):
    inbox, done = [], threading.Event()
    with client.websocket_connect("/ws") as ws:
        threading.Thread(target=collect, args=(ws, inbox, done), daemon=True).start()
        ws.send_json({"type": "hello", "videoId": "vid2", "sourceLang": "en", "targetLang": ""})
        ws.send_json({"type": "sync", "t": 0.0, "playing": True, "rate": 1.0})
        for _ in range(2):
            ws.send_bytes(pcm_silence(1.0))
            time.sleep(0.3)
        ws.send_json({"type": "sync", "t": 2.0, "playing": False, "rate": 1.0})
        time.sleep(0.2)
        before = len([m for m in inbox if m["type"] == "transcript"])
        for _ in range(5):  # silence delivered while paused must be ignored
            ws.send_bytes(pcm_silence(1.0))
        time.sleep(0.5)
        assert len([m for m in inbox if m["type"] == "transcript"]) == before
        ws.send_json({"type": "stop"})
        assert done.wait(10)
