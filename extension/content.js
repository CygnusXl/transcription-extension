// Content script (youtube.com). Renders the live transcript sidebar and subtitle overlay and tells the
// backend where the video is (play/pause/seek/rate) so transcript times line up with the video.
// It never touches audio and never opens a socket: the offscreen document does that.

(() => {
  const SIDEBAR_ID = "txe-sidebar";
  const OVERLAY_ID = "txe-overlay";

  let currentVideoId = null;
  let settings = {};
  let segments = []; // {id,start,end,text,translation?,final}
  let capturing = false;
  let dirty = true; // list needs a rebuild
  let activeId = null;
  let boundVideo = null;
  let statusKind = "off";
  let statusText = "Idle. Click the extension icon, then Start.";
  let latencyMs = null;

  // ---------- helpers ----------
  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };
  const getVideoId = () => new URL(location.href).searchParams.get("v");
  const getVideo = () => document.querySelector("video.html5-main-video") || document.querySelector("video");
  const toOffscreen = (msg) => chrome.runtime.sendMessage({ target: "offscreen", ...msg }).catch(() => {});

  // ---------- UI ----------
  function ensureSidebar() {
    let el = document.getElementById(SIDEBAR_ID);
    if (el) return el;
    el = document.createElement("div");
    el.id = SIDEBAR_ID;
    el.innerHTML = `
      <div class="txe-header">
        <span>LIVE TRANSCRIPT</span>
        <span id="txe-status" class="txe-status txe-off"></span>
      </div>
      <div id="txe-meta" class="txe-meta"></div>
      <input id="txe-search" class="txe-search" placeholder="Search transcript..." />
      <div id="txe-list" class="txe-list"></div>`;
    const host = document.querySelector("#secondary") || document.querySelector("#columns") || document.body;
    host.prepend(el);
    el.querySelector("#txe-search").addEventListener("input", () => {
      dirty = true;
      render();
    });
    paintStatus();
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

  function setStatus(kind, text) {
    statusKind = kind;
    statusText = text;
    paintStatus();
  }

  function paintStatus() {
    const s = document.getElementById("txe-status");
    if (s) {
      s.textContent = statusText;
      s.className = `txe-status txe-${statusKind}`;
    }
    const meta = document.getElementById("txe-meta");
    if (meta) {
      meta.textContent =
        capturing && latencyMs != null ? `Latency: ${(latencyMs / 1000).toFixed(1)} s` : "";
    }
  }

  function render() {
    const list = document.getElementById("txe-list");
    if (!list) return;
    if (dirty) {
      const q = (document.getElementById("txe-search")?.value || "").toLowerCase();
      list.textContent = "";
      for (const seg of segments) {
        if (q && !(seg.text + " " + (seg.translation || "")).toLowerCase().includes(q)) continue;
        const row = document.createElement("div");
        row.className = `txe-seg ${seg.final ? "txe-final" : "txe-partial"}`;
        row.dataset.id = String(seg.id);
        const time = document.createElement("div");
        time.className = "txe-time";
        time.textContent = fmt(seg.start);
        const text = document.createElement("div");
        text.className = "txe-text";
        text.textContent = seg.text;
        row.append(time, text);
        if (seg.translation) {
          const tr = document.createElement("div");
          // A translation of older (shorter) text is shown dimmed until the fresh one arrives.
          tr.className = "txe-trans" + (seg.translationOf !== seg.text ? " txe-stale" : "");
          tr.textContent = seg.translation;
          row.append(tr);
        }
        row.addEventListener("click", () => {
          const v = getVideo();
          if (v) v.currentTime = seg.start;
        });
        list.append(row);
      }
      dirty = false;
      activeId = null; // force active-row refresh below
    }
    tick();
  }

  // Cheap per-tick update: highlight the current line, scroll, update subtitles.
  function tick() {
    const video = getVideo();
    const now = video ? video.currentTime : 0;
    let active = null;
    for (const seg of segments) if (seg.start <= now + 0.3) active = seg;

    const list = document.getElementById("txe-list");
    if (list && (active ? active.id : null) !== activeId) {
      activeId = active ? active.id : null;
      list.querySelectorAll(".txe-active").forEach((n) => n.classList.remove("txe-active"));
      if (active) {
        const row = list.querySelector(`[data-id="${active.id}"]`);
        if (row) {
          row.classList.add("txe-active");
          // Scroll only the list, never the page.
          list.scrollTop = row.offsetTop - list.clientHeight / 2 + row.clientHeight / 2;
        }
      }
    }
    renderOverlay(active, now);
    paintStatus();
  }

  function renderOverlay(seg, now) {
    const el = ensureOverlay();
    if (!el) return;
    if (settings.subtitlesEnabled === false || !seg || now > seg.end + 3) {
      el.style.display = "none";
      return;
    }
    const mode = settings.subtitleMode || "original";
    const lines = [];
    if (mode !== "translation" || !seg.translation) lines.push(seg.text);
    if (mode !== "original" && seg.translation) {
      lines.push(seg.translationOf === seg.text ? seg.translation : seg.translation + " ...");
    }
    el.textContent = lines.join("\n");
    el.style.display = lines.length ? "block" : "none";
    el.style.fontSize = `${settings.fontSize || 22}px`;
    el.style.background = `rgba(0,0,0,${settings.backgroundOpacity ?? 0.6})`;
    el.style.top = settings.position === "top" ? "8%" : "auto";
    el.style.bottom = settings.position === "top" ? "auto" : "8%";
  }

  // ---------- backend messages ----------
  function upsert(msg) {
    const i = segments.findIndex((s) => s.id === msg.id);
    if (!msg.text) {
      if (i >= 0) segments.splice(i, 1); // retracted partial
    } else {
      const prev = i >= 0 ? segments[i] : null;
      const seg = {
        id: msg.id,
        start: msg.start,
        end: msg.end,
        text: msg.text,
        final: !!msg.final,
        translation: prev ? prev.translation : undefined, // keep the older translation until a new one arrives
        translationOf: prev ? prev.translationOf : undefined, // the source text that translation was made from
      };
      if (i >= 0) segments[i] = seg;
      else segments.push(seg);
      segments.sort((a, b) => a.start - b.start);
    }
    if (typeof msg.latencyMs === "number") latencyMs = msg.latencyMs;
    dirty = true;
    render();
  }

  function onBackend(p) {
    switch (p.type) {
      case "transcript":
        upsert(p);
        break;
      case "translation": {
        const seg = segments.find((s) => s.id === p.id);
        if (seg) {
          seg.translation = p.translation;
          seg.translationOf = p.text;
          dirty = true;
          render();
        }
        break;
      }
      case "status":
        if (p.state === "loading_model") setStatus("warn", "Loading speech model...");
        else if (p.state === "loading_translation") setStatus("warn", "Loading translation model...");
        else if (p.state === "listening") setStatus("ok", "Listening");
        else if (p.state === "translation_unavailable")
          setStatus("warn", "Listening (translation unavailable: " + (p.detail || "see backend log") + ")");
        else if (p.state === "error") setStatus("off", p.detail || "Backend error");
        else if (p.state === "stopped") setStatus("off", "Stopped");
        break;
    }
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.target !== "content") return;
    if (msg.type === "ws") onBackend(msg.payload);
    if (msg.type === "capture-state") onCaptureState(msg.state, msg.detail);
  });

  function onCaptureState(state, detail) {
    capturing = state === "capturing" || state === "connecting";
    if (state === "connecting") setStatus("warn", "Connecting...");
    else if (state === "capturing") {
      setStatus("warn", "Starting...");
      sendSync();
    } else if (state === "error") setStatus("off", detail || "Capture failed");
    else if (state === "idle") {
      latencyMs = null;
      setStatus("off", "Idle. Click the extension icon, then Start.");
    }
  }

  // ---------- playback sync ----------
  function sendSync() {
    const v = getVideo();
    if (!v || !capturing) return;
    toOffscreen({ type: "sync", t: v.currentTime, playing: !v.paused && !v.ended, rate: v.playbackRate });
  }

  function bindVideo() {
    const v = getVideo();
    if (!v || v === boundVideo) return;
    boundVideo = v;
    for (const ev of ["play", "pause", "seeked", "ratechange", "ended", "playing"]) v.addEventListener(ev, sendSync);
  }

  // ---------- page lifecycle ----------
  function onVideoChange() {
    bindVideo();
    const id = getVideoId();
    if (id === currentVideoId) return;
    currentVideoId = id;
    segments = [];
    dirty = true;
    if (!id) {
      document.getElementById(SIDEBAR_ID)?.remove();
      document.getElementById(OVERLAY_ID)?.remove();
      return;
    }
    ensureSidebar();
    render();
    if (capturing) toOffscreen({ type: "video", videoId: id });
  }

  async function init() {
    settings = await chrome.storage.sync.get(null);
    chrome.storage.onChanged.addListener(async () => {
      settings = await chrome.storage.sync.get(null);
      tick();
    });
    chrome.runtime.sendMessage({ target: "background", type: "get-state" }, (res) => {
      void chrome.runtime.lastError;
      const c = res && res.capture;
      if (c && c.state) onCaptureState(c.state);
    });
    onVideoChange();
    window.addEventListener("yt-navigate-finish", onVideoChange); // YouTube is a single-page app
    setInterval(onVideoChange, 1500);
    setInterval(tick, 400); // follow the playback position
    setInterval(sendSync, 1000); // heartbeat; the backend re-anchors only if the drift exceeds 1 s
  }

  init();
})();
