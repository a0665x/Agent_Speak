import { describe, expect, it, vi } from 'vitest';
import {
  createEphemeralAudioStore,
  createPlaybackAnalyser,
  createReferenceRecorder,
  encodePcm16Wav,
} from './audio';

function fakeRecorderBrowser() {
  const track = { stop: vi.fn() };
  const source = { connect: vi.fn(), disconnect: vi.fn() };
  const port = { onmessage: null as ((event: MessageEvent) => void) | null };
  const worklet = { port, disconnect: vi.fn() };
  const context = {
    state: 'running',
    audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) },
    createMediaStreamSource: vi.fn(() => source),
    close: vi.fn().mockResolvedValue(undefined),
  };
  const getUserMedia = vi.fn().mockResolvedValue({
    getTracks: () => [track],
  });
  return {
    getUserMedia,
    contextFactory: () => context as unknown as AudioContext,
    workletFactory: () => worklet as unknown as AudioWorkletNode,
    track,
    port,
  };
}

describe('ephemeral browser audio', () => {
  it('replaces and revokes the previous ephemeral reference', () => {
    const revoked: string[] = [];
    let index = 0;
    const store = createEphemeralAudioStore({
      createObjectURL: blob => `blob:${blob.size}:${index += 1}`,
      revokeObjectURL: url => revoked.push(url),
    });

    store.setReference(new Blob(['first']));
    const first = store.referenceUrl;
    store.setReference(new Blob(['second']));
    const second = store.referenceUrl;

    expect(revoked).toEqual([first]);
    store.dispose();
    expect(revoked).toEqual([first, second]);
    expect(store.referenceUrl).toBeUndefined();
  });

  it('never starts capture until start is called', async () => {
    const browser = fakeRecorderBrowser();
    const recorder = createReferenceRecorder(browser);

    expect(browser.getUserMedia).not.toHaveBeenCalled();
    await recorder.start('mic-id');

    expect(browser.getUserMedia).toHaveBeenCalledTimes(1);
    expect(browser.getUserMedia).toHaveBeenCalledWith({
      audio: { deviceId: { exact: 'mic-id' } },
      video: false,
    });
    await recorder.discard();
  });

  it('stops automatically at thirty seconds', async () => {
    vi.useFakeTimers();
    const recorder = createReferenceRecorder(fakeRecorderBrowser());
    await recorder.start('mic-id');

    await vi.advanceTimersByTimeAsync(30_000);

    expect(recorder.state).toBe('stopped');
    vi.useRealTimers();
  });

  it('encodes bounded mono PCM16 WAV headers and samples', () => {
    const wav = encodePcm16Wav(
      new Int16Array([-32_768, 0, 32_767]),
      16_000,
    );
    const view = new DataView(wav);

    expect(String.fromCharCode(...new Uint8Array(wav, 0, 4))).toBe('RIFF');
    expect(String.fromCharCode(...new Uint8Array(wav, 8, 4))).toBe('WAVE');
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint16(34, true)).toBe(16);
    expect(view.getInt16(44, true)).toBe(-32_768);
    expect(view.getInt16(48, true)).toBe(32_767);
  });

  it('reports real envelope amplitude without starting playback', async () => {
    const browser = fakeRecorderBrowser();
    const listener = vi.fn();
    const recorder = createReferenceRecorder(browser);
    recorder.subscribeAmplitude(listener);
    await recorder.start('mic-id');

    browser.port.onmessage?.({
      data: { type: 'envelope', samples: [0.01, 0.4, 0.2] },
    } as MessageEvent);

    expect(listener).toHaveBeenLastCalledWith(0.4, true);
    await recorder.discard();
  });

  it('plays only from the explicit method and reports ended cleanup', async () => {
    const listeners = new Map<string, EventListener>();
    const audio = {
      src: '',
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
      load: vi.fn(),
      addEventListener: vi.fn((name: string, listener: EventListener) => listeners.set(name, listener)),
      removeEventListener: vi.fn(),
      removeAttribute: vi.fn(),
    };
    const analyser = {
      fftSize: 0,
      connect: vi.fn(),
      getByteTimeDomainData: vi.fn(),
    };
    const source = { connect: vi.fn() };
    const context = {
      destination: {},
      createAnalyser: vi.fn(() => analyser),
      createMediaElementSource: vi.fn(() => source),
      resume: vi.fn().mockResolvedValue(undefined),
      close: vi.fn().mockResolvedValue(undefined),
    };
    const playback = createPlaybackAnalyser({
      audioFactory: () => audio as unknown as HTMLAudioElement,
      contextFactory: () => context as unknown as AudioContext,
      requestFrame: () => 1,
      cancelFrame: vi.fn(),
    });
    const ended = vi.fn();
    playback.subscribeEnded(ended);

    playback.setSource('blob:generated');
    expect(audio.play).not.toHaveBeenCalled();
    await playback.play();
    expect(audio.play).toHaveBeenCalledTimes(1);
    listeners.get('ended')?.(new Event('ended'));
    expect(ended).toHaveBeenCalledTimes(1);
    expect(playback.playing).toBe(false);
  });
});
