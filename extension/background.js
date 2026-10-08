// Background service worker (MV3).
// Stage 1/2: relays settings and checks backend health.
// Stage 3 (TODO): start tabCapture + offscreen document that streams 16 kHz PCM to the backend.

const BACKEND_HTTP = "http://127.0.0.1:8765";

const DEFAULT_SETTINGS = {
  enabled: true,
  subtitlesEnabled: false,
  subtitleMode: "original", // original | translation | both
  fontSize: 22,
  position: "bottom", // bottom | top
  backgroundOpacity: 0.6,
  sourceLang: "auto",
  targetLang: "en",
};

chrome.runtime.onInstalled.addListener(async () => {
  const existing = await chrome.storage.sync.get(null);
  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...existing });
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "health") {
    fetch(`${BACKEND_HTTP}/health`)
      .then((r) => r.json())
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // async response
  }
  return false;
});
