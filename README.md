# Transcription Extension

Chrome Extension (Manifest V3) that shows a **live, continuously updating transcript** of a YouTube video using a **local** speech recognition model, with optional local translation.

Course project: **COMP6822001 — Speech Recognition**, Final Project, 2026/2027.

```
YouTube tab audio -> Extension -> WebSocket -> localhost Python backend -> local ASR
                                                                              |
YouTube page UI (sidebar + subtitle overlay) <- WebSocket <- partial/final transcript
```

The full assignment brief is in [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md).

## Status

| Stage | Description | State |
| ----- | ----------- | ----- |
| 1 | MV3 extension, YouTube detection, transcript sidebar | Scaffolded, needs manual verification in Chrome |
| 2 | FastAPI backend + WebSocket link to the extension | Scaffolded (echo/ping), needs verification |
| 3 | Local streaming ASR (faster-whisper) | Stub only |
| 4 | Playback sync, click-to-seek, latency measurement | Sidebar click-to-seek/highlight done; latency stub |
| 5 | Local translation + language detection | Stub only |
| 6 | WER / latency / RTF experiments | Not started |
| 7 | User testing (5+ real users) | Not started |
| 8 | Finalization and packaging | Not started |

Nothing here has been measured yet. No WER, latency, or user-testing numbers exist in this repo; all such results must come from real runs.

## Repository layout

```
extension/   Chrome extension (MV3): manifest, background, content script, popup, styles
backend/     FastAPI + WebSocket server, ASR, translation, language ID, latency, SQLite cache
data/        Datasets and cached transcripts (git-ignored)
models/      Downloaded model weights (git-ignored)
experiments/ Evaluation scripts and results
tests/       Unit tests
docs/        Project brief, AI usage log
```

## Quick start

### 1. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
```

Check it: `curl http://127.0.0.1:8765/health`

### 2. Extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** and select the `extension/` folder
4. Open any `youtube.com/watch?v=...` page; a **Live Transcript** sidebar appears

The sidebar shows backend connection status. Once Stage 3 is implemented it will show partial and final transcript lines.

## Design notes

### Audio capture (Stage 3 design)

Content scripts cannot read YouTube's internal media stream, and `video.captureStream()` on a YouTube `<video>` is subject to MSE and cross-origin restrictions. The planned approach:

- Background service worker calls `chrome.tabCapture.getMediaStreamId()` after a user gesture (clicking the extension action).
- An **offscreen document** (`chrome.offscreen`) turns that stream ID into a `MediaStream`, runs an `AudioWorklet` that downsamples to 16 kHz mono PCM, and sends small chunks (about 100-250 ms) over the WebSocket.
- The backend never downloads the video; it only receives live audio chunks.

### Streaming ASR (Stage 3 design)

Candidate: `faster-whisper` (CTranslate2) with a small/medium model on the RTX 3060 Ti (8 GB), using a sliding window with local-agreement style stabilization to separate partial from finalized text. Model choice must be justified by actual benchmarks on this hardware.

### Wire protocol (JSON over WebSocket)

Client to server: `{"type":"hello","videoId":"...","sourceLang":"auto","targetLang":"en"}`, then binary PCM16 frames.
Server to client: `{"type":"transcript","id":N,"start":12.3,"end":15.1,"text":"...","final":false}`.

## AI usage

AI assistance is logged in [`docs/AI_USAGE_LOG.md`](docs/AI_USAGE_LOG.md). Every AI-generated item must be verified by the student, and AI must not produce experimental results or user-study data.
