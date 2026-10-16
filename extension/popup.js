const FIELDS = [
  "translate",
  "sourceLang",
  "targetLang",
  "subtitlesEnabled",
  "subtitleMode",
  "fontSize",
  "backgroundOpacity",
  "position",
];
const LANGUAGE_FIELDS = new Set(["translate", "sourceLang", "targetLang"]);
const $ = (id) => document.getElementById(id);

const STATE_TEXT = {
  idle: "Not running.",
  connecting: "Connecting to the local backend...",
  capturing: "Capturing tab audio. Transcript appears next to the video.",
};

function showMsg(text) {
  $("msg").textContent = text || "";
}

function renderState(capture) {
  const running = !!capture;
  $("start").style.display = running ? "none" : "block";
  $("stop").style.display = running ? "block" : "none";
  $("state").textContent = running ? STATE_TEXT[capture.state] || capture.state : STATE_TEXT.idle;
}

async function load() {
  const s = await chrome.storage.sync.get(null);
  for (const key of FIELDS) {
    const el = $(key);
    if (!el || s[key] === undefined) continue;
    if (el.type === "checkbox") el.checked = !!s[key];
    else el.value = s[key];
  }
}

function pushLanguageSettings() {
  // Applies to a running capture immediately; harmless if nothing is running.
  chrome.runtime
    .sendMessage({
      target: "offscreen",
      type: "settings",
      sourceLang: $("sourceLang").value,
      targetLang: $("translate").checked ? $("targetLang").value : "",
    })
    .catch(() => {});
}

function bind() {
  for (const key of FIELDS) {
    const el = $(key);
    el.addEventListener("input", async () => {
      let value;
      if (el.type === "checkbox") value = el.checked;
      else if (el.type === "range") value = Number(el.value);
      else value = el.value;
      await chrome.storage.sync.set({ [key]: value });
      if (LANGUAGE_FIELDS.has(key)) pushLanguageSettings();
    });
  }

  $("start").addEventListener("click", async () => {
    showMsg("");
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = (tab && tab.url) || "";
    if (!/^https:\/\/www\.youtube\.com\/watch/.test(url)) {
      showMsg("Open a YouTube video (youtube.com/watch) in this tab first.");
      return;
    }
    const videoId = new URL(url).searchParams.get("v");
    let streamId;
    try {
      // Needs the user gesture / activeTab grant that clicking in this popup provides.
      streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
    } catch (err) {
      showMsg("Cannot capture this tab: " + (err && err.message ? err.message : err));
      return;
    }
    renderState({ state: "connecting" });
    const res = await chrome.runtime.sendMessage({ target: "background", type: "start", tabId: tab.id, streamId, videoId });
    if (!res || !res.ok) {
      showMsg((res && res.error) || "Failed to start.");
      renderState(null);
    }
  });

  $("stop").addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ target: "background", type: "stop" });
    renderState(null);
  });
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.target === "popup" && msg.type === "capture-state") {
    if (msg.state === "idle") renderState(null);
    else if (msg.state === "error") {
      renderState(null);
      showMsg(msg.detail || "Capture failed.");
    } else renderState({ state: msg.state });
  }
});

function checkHealth() {
  chrome.runtime.sendMessage({ target: "background", type: "health" }, (res) => {
    const el = $("health");
    if (res && res.ok) {
      const d = res.data;
      el.textContent = d.asr_model
        ? `Backend online. ASR: ${d.asr_model} on ${d.asr_device}.`
        : `Backend online. ASR model (${d.asr_configured}) loads on first use.`;
    } else {
      el.textContent = "Backend offline. Start it: uvicorn backend.main:app --port 8765";
    }
  });
}

load().then(bind);
chrome.runtime.sendMessage({ target: "background", type: "get-state" }, (res) => renderState(res && res.capture));
checkHealth();
