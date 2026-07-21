class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(0);
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input?.length) return true;
    const combined = new Float32Array(this.buffer.length + input.length);
    combined.set(this.buffer);
    combined.set(input, this.buffer.length);
    this.buffer = combined;
    const sourceSamples = Math.round(sampleRate * 0.02);
    while (this.buffer.length >= sourceSamples) {
      const chunk = this.buffer.slice(0, sourceSamples);
      this.buffer = this.buffer.slice(sourceSamples);
      const pcm = new Int16Array(320);
      const envelope = new Float32Array(32);
      for (let index = 0; index < 320; index += 1) {
        const sourceIndex = Math.min(chunk.length - 1, Math.floor(index * chunk.length / 320));
        const sample = Math.max(-1, Math.min(1, chunk[sourceIndex]));
        pcm[index] = sample < 0 ? sample * 32768 : sample * 32767;
        const bucket = Math.min(31, Math.floor(index / 10));
        envelope[bucket] = Math.max(envelope[bucket], Math.abs(sample));
      }
      this.port.postMessage({ type: 'envelope', samples: Array.from(envelope) });
      this.port.postMessage({ type: 'pcm', buffer: pcm.buffer }, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor('pcm-capture', PcmCaptureProcessor);
