# Transcription Extension

Chrome extension (Manifest V3) that captures the **audio of a YouTube tab**, transcribes it **live with a local speech recognition model**, and optionally **translates** the transcript with a local model. Text appears next to the video and as subtitles on it while the video plays.

Course project: **COMP6822001 Speech Recognition**, Final Project, 2026/2027. The working brief is in [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md). Where it differs from the official course form, **the form wins**: see [`docs/REQUIREMENTS_CHECKLIST.md`](docs/REQUIREMENTS_CHECKLIST.md) and [`docs/REPORT_OUTLINE.md`](docs/REPORT_OUTLINE.md).

```
YouTube tab audio ──chrome.tabCapture──▶ offscreen document ──AudioWorklet──▶ 16 kHz PCM, 100 ms frames
                                                                  │ WebSocket (localhost)
                                                                  ▼
                                         Python backend: streaming ASR (faster-whisper) ──▶ partial / final lines
                                                                  │                         └─▶ local translation (NLLB-200)
                                                                  ▼
YouTube page: sidebar + subtitle overlay ◀── service worker relay ◀── transcript / translation messages
```

No cloud speech or translation service is used. Everything runs on your machine.

## Status

| Stage | Description | State |
| ----- | ----------- | ----- |
| 1 | MV3 extension, YouTube detection, transcript sidebar | Done |
| 2 | FastAPI backend + WebSocket link | Done |
| 3 | Tab-audio capture, streaming local ASR, live partial/final transcript | Implemented. Verified with real Whisper and a real Chromium, but **not yet on a real YouTube tab with `tabCapture`** (see "What has and has not been verified") |
| 4 | Playback sync, click-to-seek, latency display | Implemented. Latency is shown live; the measurement harness for the report is not written yet |
| 5 | Local translation + language detection | Implemented (NLLB-200 distilled 600M, Whisper language detection) |
| 6 | WER / CER / latency / RTF experiments | Not started |
| 7 | User testing (5+ real users) | Not started. Only you can do this |
| 8 | Finalization and packaging | Not started |

No WER, latency or user-study results exist in this repository. All such numbers must come from your own runs.

## Setup

Requires Python 3.10+, Chrome 116+, and (recommended) an NVIDIA GPU.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # for GPU torch, install the CUDA build from pytorch.org first
python -m backend.download_models          # one-time: Whisper "small" (~0.5 GB) + NLLB (~2.4 GB)
uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Check it: `curl http://127.0.0.1:8765/health`

If faster-whisper reports a missing `libcudnn` or `libcublas`, follow the CUDA 12 notes in the faster-whisper README (the `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` packages plus `LD_LIBRARY_PATH`). Use `TXE_ASR_DEVICE=cpu` to run without a GPU.

Then load the extension:

1. Open `chrome://extensions`, enable **Developer mode**, **Load unpacked**, select the `extension/` folder.
2. Open a YouTube video (`youtube.com/watch?v=...`) and play it.
3. Click the extension icon, then **Start transcribing this tab**. (Capturing a tab requires this click.)
4. A **LIVE TRANSCRIPT** panel appears above the recommendations. Turn on **Subtitles on the video** in the popup for overlay captions.

The tab stays audible while captured. Click **Stop** (or close the tab) to end the session.

## Configuration (environment variables, all optional)

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `TXE_ASR_MODEL` | `small` | faster-whisper model: `tiny`, `base`, `small`, `medium`, `large-v3-turbo`, ... |
| `TXE_ASR_DEVICE` | `auto` | `auto`, `cuda`, `cpu` |
| `TXE_ASR_COMPUTE` | `auto` | `float16` on GPU, `int8` on CPU; or set explicitly |
| `TXE_STEP_SECONDS` | `1.0` | Run inference after this much new audio (lower = more responsive, more GPU load) |
| `TXE_MAX_BUFFER_SECONDS` | `15` | Upper bound of the sliding audio window |
| `TXE_TRANSLATION_MODEL` | `facebook/nllb-200-distilled-600M` | Local translation model |
| `TXE_TRANSLATION_DEVICE` | `auto` | `auto`, `cuda`, `cpu` |
| `TXE_MODELS_DIR` | `models/` | Where models are stored |
| `TXE_DB` | `data/cache.sqlite3` | SQLite cache |

Model size is the main accuracy/latency trade-off. Comparing models on your hardware is a good first experiment for the report.

## How it works

**Audio capture.** `chrome.tabCapture` yields a stream ID after a user click. An offscreen document turns it into a `MediaStream`, plays it back so the tab stays audible, and an AudioWorklet downmixes to mono and resamples to 16 kHz in 100 ms frames, sent as int16 over a WebSocket. The WebSocket lives in the offscreen document because YouTube's CSP can block page scripts from reaching localhost.

**Streaming recognition.** Whisper is not a streaming model, so streaming is emulated with *LocalAgreement-2* (after Macháček, Dabre and Bojar, "Turning Whisper into Real-Time Transcription System", 2023): audio is buffered, and every `TXE_STEP_SECONDS` the whole window is re-transcribed with word timestamps. Words that appear in the same position in two consecutive hypotheses are **committed** (stable); the rest of the newest hypothesis is **tentative** (shown as partial, italic text and allowed to change). Committed words are grouped into lines that close at sentence end, 100 characters or 12 s. The window is trimmed as words commit, so inference time stays bounded. Context text for the decoder only includes words that have already left the window; including text still inside the window made Whisper skip audio it believed was done.

**Timing.** The content script reports play/pause/seek/rate changes (plus a 1 s heartbeat). The backend keeps a mapping from its audio clock to the video clock, so transcript times are video times. Audio received while the video is paused is ignored; a seek finalises the current line and restarts the window.

**Translation.** Finalised lines are translated with NLLB-200 and keep the ASR timestamps. The open (partial) line is re-translated at most about once per 1.2 s. A translation of older text is shown dimmed until the fresh one arrives. Changing the target language re-translates the lines on screen.

**Latency.** Each transcript message carries `latencyMs` (newest displayed word: time since that audio was captured, measured on the backend's clock) and `stableLatencyMs` (newest committed word). These exclude delay before the audio reaches the backend (tab capture and worklet buffering, typically small but not measured).

**Cache.** Finalised lines and translations are stored in SQLite after they are shown live. Nothing is replayed from the cache, so the real-time pipeline always runs.

### WebSocket protocol

Client to server (text): `hello {videoId, sourceLang, targetLang}`, `settings`, `sync {t, playing, rate}`, `video {videoId}`, `stop`. Client to server (binary): int16 mono 16 kHz PCM.

Server to client: `ack`, `status {state, detail}`, `transcript {id, start, end, text, final, lang, latencyMs, stableLatencyMs}` (same `id` = update in place; empty `text` = remove), `translation {id, text, translation, target}`.

## Tests

```bash
pytest                              # algorithm, protocol (fake model), database, latency clock
node tests/worklet.test.js          # AudioWorklet resampler
```

The WebSocket test uses a scripted fake model so it needs no GPU or download.

## What has and has not been verified

Verified during development (in a CPU-only Linux sandbox, with `base` Whisper and NLLB-600M):

- Unit and protocol tests pass.
- A real 13 s speech clip streamed through the real backend over a real WebSocket produces partial text that updates, then final text.
- The extension loads in Chromium; the sidebar, subtitle overlay, search and click-to-seek work on a stand-in YouTube page; audio flows offscreen document, AudioWorklet, WebSocket, backend, service worker relay, page.
- Real NLLB translation works for en/id/ja/ko/es/de pairs.

**Not verified** (needs your machine):

- `chrome.tabCapture` on a real YouTube tab, including real YouTube layout and ads (ad audio is part of the tab audio).
- Behaviour and speed on your RTX 3060 Ti. Do not quote any latency from the development checks: they are CPU numbers.
- Accuracy on your test videos.

## Known limitations

- One capture at a time; capturing is tied to the tab it was started from.
- Whisper can hallucinate on music or silence; VAD filtering reduces but does not remove this.
- Technical terms are weak spots for both models. In a quick check NLLB rendered Korean 합성곱 신경망 ("convolutional neural network") as "synthetic square neural networks". Measure this properly for the error analysis.
- `faster_whisper.decode_audio` may fail with some PyAV versions (`metadata_errors`). The backend does not use it; for offline evaluation scripts read audio with `soundfile` or `librosa`.

## AI usage

The course form sets **AI Use Type: Integrated**: AI is allowed, but every material use must be logged ([`docs/AI_USAGE_LOG.md`](docs/AI_USAGE_LOG.md)), verified by you, and explainable at the demo. AI must not produce experimental results, WER/latency numbers, or user-study data. The report must end with the AI Usage Declaration.
