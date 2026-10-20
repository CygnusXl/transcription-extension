// Service worker. Coordinates capture and relays messages; holds no long-lived state in memory
// (MV3 service workers are stopped when idle), so the active capture is kept in storage.session.
//
// Message routing uses a `target` field:
//   popup/content -> background   target:"background"   start | stop | get-state
//   background    -> offscreen    target:"offscreen"    start | stop
//   offscreen     -> background   target:"background"   ws | capture-status
//   background    -> content      target:"content"      ws | capture-state       (tabs.sendMessage)
//   background    -> popup        target:"popup"        capture-state

const BACKEND_HTTP = "http://127.0.0.1:8765";

const DEFAULT_SETTINGS = {
  translate: true,
  sourceLang: "auto",
  targetLang: "en",
  subtitlesEnabled: true,
  subtitleMode: "original", // original | translation | both
  fontSize: 22,
  position: "bottom", // bottom | top
  backgroundOpacity: 0.35,
};

chrome.runtime.onInstalled.addListener(async () => {
  const existing = await chrome.storage.sync.get(null);
  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...existing });
});

const getCapture = async () => (await chrome.storage.session.get("capture")).capture || null;
const setCapture = (c) => (c ? chrome.storage.session.set({ capture: c }) : chrome.storage.session.remove("capture"));

async function ensureOffscreen() {
  if (await chrome.offscreen.hasDocument()) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["USER_MEDIA"],
    justification: "Capture the tab's audio stream and send it to the local speech recognition backend.",
  });
}

function notify(tabId, message) {
  if (tabId != null) chrome.tabs.sendMessage(tabId, { target: "content", ...message }).catch(() => {});
  chrome.runtime.sendMessage({ target: "popup", ...message }).catch(() => {});
}

async function startCapture({ tabId, streamId, videoId }) {
  if (await getCapture()) await stopCapture();
  await ensureOffscreen();
  const s = await chrome.storage.sync.get(null);
  await setCapture({ tabId, state: "connecting" });
  const res = await chrome.runtime.sendMessage({
    target: "offscreen",
    type: "start",
    tabId,
    streamId,
    videoId,
    settings: { sourceLang: s.sourceLang, targetLang: s.translate ? s.targetLang : "" },
  });
  if (!res || !res.ok) {
    await setCapture(null);
    throw new Error((res && res.error) || "Could not start audio capture.");
  }
}

async function stopCapture() {
  const capture = await getCapture();
  if (!capture) return;
  try {
    await chrome.runtime.sendMessage({ target: "offscreen", type: "stop" });
  } catch {}
  await setCapture(null);
  try {
    await chrome.offscreen.closeDocument();
  } catch {}
  notify(capture.tabId, { type: "capture-state", state: "idle" });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.target !== "background") return false;

  if (msg.type === "start") {
    startCapture(msg)
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err && err.message ? err.message : err) }));
    return true;
  }
  if (msg.type === "stop") {
    stopCapture().then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg.type === "get-state") {
    getCapture().then((capture) => sendResponse({ capture }));
    return true;
  }
  if (msg.type === "health") {
    fetch(`${BACKEND_HTTP}/health`)
      .then((r) => r.json())
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  if (msg.type === "ws") {
    notify(msg.tabId, { type: "ws", payload: msg.payload });
    return false;
  }
  if (msg.type === "capture-status") {
    (async () => {
      const capture = await getCapture();
      if (msg.state === "error") await setCapture(null);
      else if (capture) await setCapture({ ...capture, state: msg.state });
      notify(msg.tabId, { type: "capture-state", state: msg.state, detail: msg.detail });
    })();
    return false;
  }
  return false;
});

// Stop when the captured tab is closed.
chrome.tabs.onRemoved.addListener(async (tabId) => {
  const capture = await getCapture();
  if (capture && capture.tabId === tabId) await stopCapture();
});
