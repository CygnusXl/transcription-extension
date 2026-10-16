// Run: node tests/worklet.test.js
// Checks that the AudioWorklet downsampler produces 16 kHz mono frames of the right size and pitch.
const assert = require("node:assert");

function makeProcessor(rate) {
  global.sampleRate = rate;
  global.AudioWorkletProcessor = class {
    constructor() {
      this.posted = [];
      this.port = { postMessage: (data) => this.posted.push(data) };
    }
  };
  delete require.cache[require.resolve("../extension/pcm-worklet.js")];
  const { PcmDownsampler } = require("../extension/pcm-worklet.js");
  return new PcmDownsampler({ processorOptions: { targetRate: 16000, frameSamples: 1600 } });
}

function run(rate, hz, seconds, channels) {
  const p = makeProcessor(rate);
  const total = Math.floor(rate * seconds);
  const block = 128; // the Web Audio render quantum
  for (let start = 0; start + block <= total; start += block) {
    const input = [];
    for (let c = 0; c < channels; c++) {
      const buf = new Float32Array(block);
      for (let i = 0; i < block; i++) buf[i] = 0.5 * Math.sin((2 * Math.PI * hz * (start + i)) / rate);
      input.push(buf);
    }
    assert.strictEqual(p.process([input]), true);
  }
  return p.posted;
}

for (const rate of [48000, 44100]) {
  for (const channels of [1, 2]) {
    const frames = run(rate, 1000, 2.0, channels);
    // ~2 s of audio at 16 kHz in 1600-sample frames = ~20 frames (a partial last frame is held back)
    assert.ok(frames.length >= 19 && frames.length <= 20, `rate ${rate}: got ${frames.length} frames`);
    for (const f of frames) assert.strictEqual(f.length, 1600);

    const samples = Float32Array.from(frames.flatMap((f) => Array.from(f)));
    // 1 kHz at 16 kHz -> 16 samples per cycle -> 2 zero crossings per cycle
    let crossings = 0;
    for (let i = 1; i < samples.length; i++) if (samples[i - 1] < 0 !== samples[i] < 0) crossings++;
    const hzEstimate = (crossings / 2) * (16000 / samples.length);
    assert.ok(Math.abs(hzEstimate - 1000) < 15, `rate ${rate}: pitch ${hzEstimate.toFixed(1)} Hz`);

    const rms = Math.sqrt(samples.reduce((a, s) => a + s * s, 0) / samples.length);
    assert.ok(Math.abs(rms - 0.5 / Math.SQRT2) < 0.03, `rate ${rate}: rms ${rms.toFixed(3)}`);
  }
}
console.log("worklet resampler OK (48 kHz and 44.1 kHz, mono and stereo)");
