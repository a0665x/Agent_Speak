type ObjectUrlFactory = {
  createObjectURL(blob: Blob): string;
  revokeObjectURL(url: string): void;
};

export type EphemeralAudioStore = {
  readonly reference?: Blob;
  readonly generated?: Blob;
  readonly referenceUrl?: string;
  readonly generatedUrl?: string;
  setReference(blob: Blob): void;
  clearReference(): void;
  setGenerated(blob: Blob): void;
  clearGenerated(): void;
  dispose(): void;
};

export function createEphemeralAudioStore(
  urls: ObjectUrlFactory = URL,
): EphemeralAudioStore {
  let reference: Blob | undefined;
  let generated: Blob | undefined;
  let referenceUrl: string | undefined;
  let generatedUrl: string | undefined;

  const revoke = (url: string | undefined) => {
    if (url) urls.revokeObjectURL(url);
  };

  return {
    get reference() { return reference; },
    get generated() { return generated; },
    get referenceUrl() { return referenceUrl; },
    get generatedUrl() { return generatedUrl; },
    setReference(blob) {
      revoke(referenceUrl);
      reference = blob;
      referenceUrl = urls.createObjectURL(blob);
    },
    clearReference() {
      revoke(referenceUrl);
      reference = undefined;
      referenceUrl = undefined;
    },
    setGenerated(blob) {
      revoke(generatedUrl);
      generated = blob;
      generatedUrl = urls.createObjectURL(blob);
    },
    clearGenerated() {
      revoke(generatedUrl);
      generated = undefined;
      generatedUrl = undefined;
    },
    dispose() {
      revoke(referenceUrl);
      revoke(generatedUrl);
      reference = undefined;
      generated = undefined;
      referenceUrl = undefined;
      generatedUrl = undefined;
    },
  };
}

type RecorderOptions = {
  getUserMedia?: (constraints: MediaStreamConstraints) => Promise<MediaStream>;
  contextFactory?: () => AudioContext;
  workletFactory?: (context: AudioContext) => AudioWorkletNode;
  workletUrl?: string;
  maxDurationMs?: number;
  voicedThreshold?: number;
};

export type ReferenceRecorder = {
  readonly state: 'idle' | 'recording' | 'stopped';
  start(deviceId: string): Promise<void>;
  stop(): Promise<Blob>;
  discard(): Promise<void>;
  subscribeAmplitude(
    listener: (value: number, voiced: boolean) => void,
  ): () => void;
};

export function createReferenceRecorder(
  options: RecorderOptions = {},
): ReferenceRecorder {
  const getUserMedia = options.getUserMedia
    ?? (constraints => navigator.mediaDevices.getUserMedia(constraints));
  const contextFactory = options.contextFactory ?? (() => new AudioContext());
  const workletFactory = options.workletFactory
    ?? (context => new AudioWorkletNode(context, 'pcm-capture'));
  const workletUrl = options.workletUrl ?? '/tts_clone_test/pcm-capture.worklet.js';
  const maxDurationMs = options.maxDurationMs ?? 30_000;
  const voicedThreshold = options.voicedThreshold ?? 0.03;

  let state: ReferenceRecorder['state'] = 'idle';
  let stream: MediaStream | undefined;
  let context: AudioContext | undefined;
  let source: MediaStreamAudioSourceNode | undefined;
  let worklet: AudioWorkletNode | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let frames: Int16Array[] = [];
  let lastBlob: Blob | undefined;
  let stopping: Promise<Blob> | undefined;
  const listeners = new Set<(value: number, voiced: boolean) => void>();

  const cleanup = async () => {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
    worklet?.disconnect();
    source?.disconnect();
    worklet = undefined;
    source = undefined;
    stream?.getTracks().forEach(track => track.stop());
    stream = undefined;
    const activeContext = context;
    context = undefined;
    if (activeContext && activeContext.state !== 'closed') {
      await activeContext.close();
    }
  };

  const stop = async (): Promise<Blob> => {
    if (stopping) return stopping;
    if (state === 'stopped' && lastBlob) return lastBlob;
    if (state !== 'recording') throw new Error('Reference recorder is not active');
    stopping = (async () => {
      state = 'stopped';
      await cleanup();
      const sampleCount = frames.reduce((total, frame) => total + frame.length, 0);
      const samples = new Int16Array(sampleCount);
      let offset = 0;
      for (const frame of frames) {
        samples.set(frame, offset);
        offset += frame.length;
      }
      lastBlob = new Blob([encodePcm16Wav(samples, 16_000)], { type: 'audio/wav' });
      frames = [];
      stopping = undefined;
      return lastBlob;
    })();
    return stopping;
  };

  return {
    get state() { return state; },
    async start(deviceId) {
      if (state === 'recording') throw new Error('Reference recorder is already active');
      await cleanup();
      frames = [];
      lastBlob = undefined;
      stopping = undefined;
      const constraints: MediaStreamConstraints = {
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
        video: false,
      };
      try {
        stream = await getUserMedia(constraints);
        context = contextFactory();
        await context.audioWorklet.addModule(workletUrl);
        source = context.createMediaStreamSource(stream);
        worklet = workletFactory(context);
        worklet.port.onmessage = event => {
          if (event.data?.type === 'pcm' && event.data.buffer instanceof ArrayBuffer) {
            frames.push(new Int16Array(event.data.buffer.slice(0)));
          } else if (event.data?.type === 'envelope' && Array.isArray(event.data.samples)) {
            const amplitude = Math.max(0, Math.min(
              1,
              Math.max(...event.data.samples.map((value: unknown) => Number(value) || 0)),
            ));
            listeners.forEach(listener => listener(
              amplitude,
              amplitude >= voicedThreshold,
            ));
          }
        };
        source.connect(worklet);
        state = 'recording';
        timer = setTimeout(() => { void stop(); }, maxDurationMs);
      } catch (error) {
        await cleanup();
        state = 'idle';
        throw error;
      }
    },
    stop,
    async discard() {
      await cleanup();
      frames = [];
      lastBlob = undefined;
      stopping = undefined;
      state = 'idle';
      listeners.forEach(listener => listener(0, false));
    },
    subscribeAmplitude(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export function encodePcm16Wav(samples: Int16Array, sampleRate: number): ArrayBuffer {
  const buffer = new ArrayBuffer(44 + samples.byteLength);
  const view = new DataView(buffer);
  const writeAscii = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };
  writeAscii(0, 'RIFF');
  view.setUint32(4, 36 + samples.byteLength, true);
  writeAscii(8, 'WAVE');
  writeAscii(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, 'data');
  view.setUint32(40, samples.byteLength, true);
  new Uint8Array(buffer, 44).set(
    new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength),
  );
  return buffer;
}

type PlaybackOptions = {
  audioFactory?: () => HTMLAudioElement;
  contextFactory?: () => AudioContext;
  requestFrame?: (callback: FrameRequestCallback) => number;
  cancelFrame?: (handle: number) => void;
};

export type PlaybackAnalyser = {
  readonly playing: boolean;
  setSource(url: string): void;
  play(): Promise<void>;
  stop(): void;
  subscribeAmplitude(listener: (value: number) => void): () => void;
  subscribeEnded(listener: () => void): () => void;
  dispose(): void;
};

export function createPlaybackAnalyser(
  options: PlaybackOptions = {},
): PlaybackAnalyser {
  const audio = options.audioFactory?.() ?? new Audio();
  const contextFactory = options.contextFactory ?? (() => new AudioContext());
  const requestFrame = options.requestFrame ?? requestAnimationFrame;
  const cancelFrame = options.cancelFrame ?? cancelAnimationFrame;
  const listeners = new Set<(value: number) => void>();
  const endedListeners = new Set<() => void>();
  let context: AudioContext | undefined;
  let analyser: AnalyserNode | undefined;
  let frame = 0;
  let playing = false;

  const sample = () => {
    if (!playing || !analyser) return;
    const values = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(values);
    let energy = 0;
    values.forEach(value => { energy += ((value - 128) / 128) ** 2; });
    const amplitude = Math.min(1, Math.sqrt(energy / values.length));
    listeners.forEach(listener => listener(amplitude));
    frame = requestFrame(sample);
  };
  const stop = () => {
    playing = false;
    if (frame) cancelFrame(frame);
    frame = 0;
    audio.pause();
    listeners.forEach(listener => listener(0));
  };
  const ended = () => {
    stop();
    endedListeners.forEach(listener => listener());
  };
  audio.addEventListener('ended', ended);

  return {
    get playing() { return playing; },
    setSource(url) {
      stop();
      audio.src = url;
      audio.load();
    },
    async play() {
      if (!audio.src) throw new Error('Generated audio is not ready');
      if (!context) {
        context = contextFactory();
        analyser = context.createAnalyser();
        analyser.fftSize = 256;
        context.createMediaElementSource(audio).connect(analyser);
        analyser.connect(context.destination);
      }
      await context.resume();
      await audio.play();
      playing = true;
      frame = requestFrame(sample);
    },
    stop,
    subscribeAmplitude(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    subscribeEnded(listener) {
      endedListeners.add(listener);
      return () => endedListeners.delete(listener);
    },
    dispose() {
      stop();
      audio.removeEventListener('ended', ended);
      audio.removeAttribute('src');
      audio.load();
      void context?.close();
      context = undefined;
      analyser = undefined;
      listeners.clear();
      endedListeners.clear();
    },
  };
}
