// AudioWorklet: downmix to mono, resample to 16 kHz with a box filter, emit fixed-size Float32 frames.
// Runs on the audio rendering thread. The processor writes nothing to its output (silence), so it
// can be connected to the destination without doubling the sound.

class PcmDownsampler extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const o = (options && options.processorOptions) || {};
    this.targetRate = o.targetRate || 16000;
    this.frameSamples = o.frameSamples || 1600; // 100 ms at 16 kHz
    this.ratio = sampleRate / this.targetRate; // input samples per output sample (may be fractional)
    this.out = new Float32Array(this.frameSamples);
    this.n = 0; // samples written into `out`
    this.acc = 0; // running sum for the current output sample
    this.cnt = 0; // input samples accumulated
    this.phase = 0; // fractional position inside the current output sample
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channels = input.length;
    const len = input[0].length;
    for (let i = 0; i < len; i++) {
      let s = 0;
      for (let c = 0; c < channels; c++) s += input[c][i];
      this.acc += s / channels;
      this.cnt += 1;
      this.phase += 1;
      if (this.phase >= this.ratio) {
        this.out[this.n++] = this.acc / this.cnt;
        this.acc = 0;
        this.cnt = 0;
        this.phase -= this.ratio;
        if (this.n === this.frameSamples) {
          this.port.postMessage(this.out, [this.out.buffer]); // transfer, no copy
          this.out = new Float32Array(this.frameSamples);
          this.n = 0;
        }
      }
    }
    return true;
  }
}

if (typeof registerProcessor === "function") {
  registerProcessor("pcm-downsampler", PcmDownsampler);
}
if (typeof module !== "undefined") {
  module.exports = { PcmDownsampler };
}
