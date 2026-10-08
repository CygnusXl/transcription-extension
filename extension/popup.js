const FIELDS = [
  "enabled",
  "subtitlesEnabled",
  "subtitleMode",
  "sourceLang",
  "targetLang",
  "fontSize",
  "backgroundOpacity",
  "position",
];

async function load() {
  const s = await chrome.storage.sync.get(null);
  for (const key of FIELDS) {
    const el = document.getElementById(key);
    if (!el || s[key] === undefined) continue;
    if (el.type === "checkbox") el.checked = !!s[key];
    else el.value = s[key];
  }
}

function bind() {
  for (const key of FIELDS) {
    const el = document.getElementById(key);
    el.addEventListener("input", () => {
      let value;
      if (el.type === "checkbox") value = el.checked;
      else if (el.type === "range") value = Number(el.value);
      else value = el.value;
      chrome.storage.sync.set({ [key]: value });
    });
  }
}

function checkHealth() {
  chrome.runtime.sendMessage({ type: "health" }, (res) => {
    const el = document.getElementById("health");
    if (res?.ok) el.textContent = `Backend: online (ASR: ${res.data.asr_model || "not loaded"})`;
    else el.textContent = "Backend: offline. Start it with uvicorn.";
  });
}

load().then(bind);
checkHealth();
