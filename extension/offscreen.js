// Offscreen document: owns the tab-audio stream and the single WebSocket to the local backend.
//
//   tab audio --getUserMedia(chromeMediaSource:'tab')--> AudioContext
//        |--> destination                     (keeps the tab audible; capture mutes it otherwise)
//        '--> AudioWorklet (mono, 16 kHz, 100 ms frames) --> int16 --> WebSocket --> backend
//
// Backend messages are forwarded to the service worker, which relays them to the YouTube tab.
// (The WebSocket lives here, not in the content script, because YouTube's CSP can block
// connections to localhost from page-context scripts.)

const WS_URL = "ws://127.0.0.1:8765/ws";
const MAX_BUFFERED_BYTES = 1_000_000; // drop frames rather than let a stalled backend build a backlog

let ws = null;
let stream = null;
let audioCtx = null;
let node = null;
let tabId = null;
let stoppedWaiter = null;

const report = (state, detail) =>
  chrome.runtime.sendMessage({ target: "background", type: "capture-status", tabId, state, detail }).catch(() => {});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.target !== "offscreen") return false;
  switch (msg.type) {
    case "start":
      start(msg)
        .then(() => sendResponse({ ok: true }))
        .catch((err) => {
          const message = String(err && err.message ? err.message : err);
          report("error", message);
          stop().finally(() => sendResponse({ ok: false, error: message })); // also closes the socket
        });
      return true; // async response
    case "stop":
      stop().then(() => sendResponse({ ok: true }));
      return true;
    case "settings":
      send({ type: "settings", sourceLang: msg.sourceLang, targetLang: msg.targetLang });
      break;
    case "sync":
      send({ type: "sync", t: msg.t, playing: msg.playing, rate: msg.rate });
      break;
    case "video":
      send({ type: "video", videoId: msg.videoId });
      break;
  }
  return false;
});

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function openSocket(hello) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(WS_URL);
    socket.binaryType = "arraybuffer";
    socket.onopen = () => {
      ws = socket;
      send(hello);
      resolve();
    };
    socket.onerror = () => reject(new Error("Cannot reach the local backend at 127.0.0.1:8765. Is it running?"));
    socket.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      let payload;
      try {
        payload = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (payload.type === "status" && payload.state === "stopped" && stoppedWaiter) stoppedWaiter();
      chrome.runtime.sendMessage({ target: "background", type: "ws", tabId, payload }).catch(() => {});
    };
    socket.onclose = () => {
      if (ws === socket) {
        ws = null;
        if (stream) {
          // Unexpected: backend went away while capturing. Release the tab so its audio returns to normal.
          cleanup();
          report("error", "Connection to the local backend was lost.");
        }
      }
    };
  });
}

async function start({ streamId, tabId: tid, videoId, settings }) {
  await stop();
  tabId = tid;
  report("connecting");

  await openSocket({
    type: "hello",
    videoId,
    sourceLang: (settings && settings.sourceLang) || "auto",
    targetLang: (settings && settings.targetLang) || "",
  });

  stream = await navigator.mediaDevices.getUserMedia({
    audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } },
    video: false,
  });

  audioCtx = new AudioContext();
  await audioCtx.audioWorklet.addModule("pcm-worklet.js");
  const source = audioCtx.createMediaStreamSource(stream);
  source.connect(audioCtx.destination); // the user keeps hearing the video

  node = new AudioWorkletNode(audioCtx, "pcm-downsampler", {
    processorOptions: { targetRate: 16000, frameSamples: 1600 },
  });
  node.port.onmessage = (ev) => {
    if (!ws || ws.readyState !== WebSocket.OPEN || ws.bufferedAmount > MAX_BUFFERED_BYTES) return;
    const f32 = ev.data;
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]));
      i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    ws.send(i16.buffer);
  };
  source.connect(node);
  node.connect(audioCtx.destination); // silent output; keeps the node in the audio graph

  report("capturing");
}

function cleanup() {
  try {
    if (node) node.disconnect();
  } catch {}
  if (stream) stream.getTracks().forEach((t) => t.stop());
  if (audioCtx) audioCtx.close().catch(() => {});
  node = null;
  stream = null;
  audioCtx = null;
}

async function stop() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const socket = ws;
    // Ask the backend to finalise the current line, and give it a moment to answer.
    const finalised = new Promise((resolve) => {
      stoppedWaiter = resolve;
      setTimeout(resolve, 4000);
    });
    send({ type: "stop" });
    await finalised;
    stoppedWaiter = null;
    ws = null;
    socket.close();
  }
  cleanup();
}
