// Content script: runs on youtube.com.
// Detects the current video, injects the transcript sidebar and subtitle overlay,
// connects to the local backend over WebSocket, and renders transcript segments.

(() => {
  const WS_URL = "ws://127.0.0.1:8765/ws";
  const SIDEBAR_ID = "txe-sidebar";
  const OVERLAY_ID = "txe-overlay";

  let currentVideoId = null;
  let ws = null;
  let settings = {};
  /** @type {Array<{id:number,start:number,end:number,text:string,translation?:string,final:boolean}>} */
  let segments = [];

  // ---------- helpers ----------
  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  const getVideoId = () => new URL(location.href).searchParams.get("v");
  const getVideo = () => document.querySelector("video.html5-main-video");

  // ---------- UI ----------
  function ensureSidebar() {
    let el = document.getElementById(SIDEBAR_ID);
    if (el) return el;
    el = document.createElement("div");
    el.id = SIDEBAR_ID;
    el.innerHTML = `
      <div class="txe-header">
        <span>LIVE TRANSCRIPT</span>
        <span id="txe-status" class="txe-status txe-off">disconnected</span>
      </div>
      <input id="txe-search" class="txe-search" placeholder="Search transcript..." />
      <div id="txe-list" class="txe-list"></div>`;
    const host =
      document.querySelector("#secondary") || document.querySelector("#columns") || document.body;
    host.prepend(el);
    el.querySelector("#txe-search").addEventListener("input", render);
    return el;
  }

  function ensureOverlay() {
    let el = document.getElementById(OVERLAY_ID);
    if (el) return el;
    const player = document.querySelector("#movie_player");
    if (!player) return null;
    el = document.createElement("div");
    el.id = OVERLAY_ID;
    player.appendChild(el);
    return el;
  }

  function setStatus(text, ok) {
    const s = document.getElementById("txe-status");
    if (!s) return;
    s.textContent = text;
    s.className = `txe-status ${ok ? "txe-on" : "txe-off"}`;
  }

  function render() {
    const list = document.getElementById("txe-list");
    if (!list) return;
    const q = (document.getElementById("txe-search")?.value || "").toLowerCase();
    const video = getVideo();
    const now = video ? video.currentTime : 0;
    list.innerHTML = "";
    for (const seg of segments) {
      if (q && !(seg.text + " " + (seg.translation || "")).toLowerCase().includes(q)) continue;
      const row = document.createElement("div");
      const active = now >= seg.start && now <= seg.end;
      row.className = `txe-seg ${seg.final ? "txe-final" : "txe-partial"} ${active ? "txe-active" : ""}`;
      row.innerHTML = `<div class="txe-time">${fmt(seg.start)}</div>
        <div class="txe-text"></div>
        ${seg.translation ? '<div class="txe-trans"></div>' : ""}`;
      row.querySelector(".txe-text").textContent = seg.text;
      if (seg.translation) row.querySelector(".txe-trans").textContent = seg.translation;
      row.addEventListener("click", () => {
        const v = getVideo();
        if (v) v.currentTime = seg.start;
      });
      list.appendChild(row);
    }
    const active = list.querySelector(".txe-active");
    if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
    renderOverlay(now);
  }

  function renderOverlay(now) {
    const el = ensureOverlay();
    if (!el) return;
    if (!settings.subtitlesEnabled) {
      el.style.display = "none";
      return;
    }
    const seg = segments.find((s) => now >= s.start && now <= s.end) || segments[segments.length - 1];
    if (!seg) {
      el.style.display = "none";
      return;
    }
    const parts = [];
    if (settings.subtitleMode !== "translation") parts.push(seg.text);
    if (settings.subtitleMode !== "original" && seg.translation) parts.push(seg.translation);
    el.textContent = parts.join("\n");
    el.style.display = parts.length ? "block" : "none";
    el.style.fontSize = `${settings.fontSize || 22}px`;
    el.style.background = `rgba(0,0,0,${settings.backgroundOpacity ?? 0.6})`;
    el.style.top = settings.position === "top" ? "8%" : "auto";
    el.style.bottom = settings.position === "top" ? "auto" : "8%";
  }

  // ---------- transcript handling ----------
  function upsertSegment(msg) {
    const i = segments.findIndex((s) => s.id === msg.id);
    const seg = {
      id: msg.id,
      start: msg.start,
      end: msg.end,
      text: msg.text,
      translation: msg.translation,
      final: !!msg.final,
    };
    if (i >= 0) segments[i] = seg;
    else segments.push(seg);
    segments.sort((a, b) => a.start - b.start);
    render();
  }

  // ---------- backend connection ----------
  function connect() {
    if (ws) ws.close();
    if (!currentVideoId || !settings.enabled) return;
    ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      setStatus("connected", true);
      ws.send(
        JSON.stringify({
          type: "hello",
          videoId: currentVideoId,
          sourceLang: settings.sourceLang,
          targetLang: settings.targetLang,
        })
      );
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      const msg = JSON.parse(ev.data);
      if (msg.type === "transcript") upsertSegment(msg);
    };
    ws.onclose = () => setStatus("disconnected", false);
    ws.onerror = () => setStatus("backend unreachable", false);
  }

  // ---------- page lifecycle ----------
  function onVideoChange() {
    const id = getVideoId();
    if (id === currentVideoId) return;
    currentVideoId = id;
    segments = [];
    if (!id) {
      document.getElementById(SIDEBAR_ID)?.remove();
      document.getElementById(OVERLAY_ID)?.remove();
      ws?.close();
      return;
    }
    ensureSidebar();
    render();
    connect();
  }

  async function init() {
    settings = await chrome.storage.sync.get(null);
    chrome.storage.onChanged.addListener(async () => {
      settings = await chrome.storage.sync.get(null);
      render();
    });
    onVideoChange();
    // YouTube is a single-page app: react to its navigation event and poll as a fallback.
    window.addEventListener("yt-navigate-finish", onVideoChange);
    setInterval(onVideoChange, 1500);
    setInterval(render, 500); // follow playback position
  }

  init();
})();
