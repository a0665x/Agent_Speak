import { checkAudioDevices, watchDeviceChanges } from './deviceGate';
import type { DeviceGateResult, RealtimeEvent } from '../types';

type ClientOptions = {
  mediaDevices?: MediaDevices;
  socketFactory?: (url: string) => WebSocket;
  contextFactory?: () => AudioContext;
  workletFactory?: (context: AudioContext) => AudioWorkletNode;
  onEvent?: (event: RealtimeEvent | { type: string; data: Record<string, unknown> }) => void;
};

export class RealtimeClient {
  private readonly mediaDevices?: MediaDevices;
  private readonly socketFactory: (url: string) => WebSocket;
  private readonly contextFactory: () => AudioContext;
  private readonly workletFactory: (context: AudioContext) => AudioWorkletNode;
  private readonly onEvent: NonNullable<ClientOptions['onEvent']>;
  private gate: DeviceGateResult = { ready: false, reason: 'unchecked' };
  private stream?: MediaStream;
  private socket?: WebSocket;
  private context?: AudioContext;
  private source?: MediaStreamAudioSourceNode;
  private worklet?: AudioWorkletNode;
  private unwatch?: () => void;

  constructor(options: ClientOptions = {}) {
    this.mediaDevices = options.mediaDevices ?? globalThis.navigator?.mediaDevices;
    this.socketFactory = options.socketFactory ?? (url => new WebSocket(url));
    this.contextFactory = options.contextFactory ?? (() => new AudioContext());
    this.workletFactory = options.workletFactory ?? (context => new AudioWorkletNode(context, 'pcm-capture'));
    this.onEvent = options.onEvent ?? (() => undefined);
  }

  async checkDevices(expectedLabel = 'Zone Vibe 100'): Promise<DeviceGateResult> {
    if (!this.mediaDevices) {
      this.gate = { ready: false, reason: 'permission_denied' };
      return this.gate;
    }
    this.gate = await checkAudioDevices(this.mediaDevices, expectedLabel);
    this.unwatch?.();
    this.unwatch = watchDeviceChanges(this.mediaDevices, () => {
      this.gate = { ready: false, reason: 'unchecked' };
      this.onEvent({ type: 'device.invalidated', data: {} });
      void this.stop('devicechange');
    });
    this.onEvent({
      type: this.gate.ready ? 'device.ready' : 'device.unavailable',
      data: {
        reason: this.gate.reason,
        input: this.gate.input?.label,
        output: this.gate.output?.label
      }
    });
    return this.gate;
  }

  approveForTest(gate: DeviceGateResult): void {
    this.gate = gate;
  }

  async start(sessionId: string): Promise<void> {
    if (!this.gate.ready || !this.gate.input || !this.mediaDevices) {
      throw new Error('Device gate is not approved');
    }
    if (this.stream || this.socket) throw new Error('Realtime client is already active');
    try {
      this.stream = await this.mediaDevices.getUserMedia({
        audio: { deviceId: { exact: this.gate.input.deviceId } },
        video: false
      });
      this.context = this.contextFactory();
      await this.context.audioWorklet.addModule('/asr_realtime/pcm-capture.worklet.js');
      this.source = this.context.createMediaStreamSource(this.stream);
      this.worklet = this.workletFactory(this.context);
      this.socket = this.socketFactory(this.socketUrl(sessionId));
      await socketReady(this.socket);
      this.socket.send(JSON.stringify({
        type: 'stream.start',
        format: 'pcm_s16le',
        sample_rate: 16000,
        channels: 1,
        frame_ms: 20
      }));
      this.socket.addEventListener('message', event => this.handleSocketMessage(event));
      this.socket.addEventListener('error', () => void this.stop('socket_error'));
      this.socket.addEventListener('close', () => void this.stop('socket_closed'));
      this.worklet.port.onmessage = event => {
        if (event.data?.type === 'pcm' && this.socket?.readyState === 1) {
          this.socket.send(event.data.buffer as ArrayBuffer);
        } else if (event.data?.type === 'envelope') {
          this.onEvent({ type: 'audio.envelope', data: { samples: event.data.samples } });
        } else if (event.data?.type === 'error') {
          void this.stop('worklet_error');
        }
      };
      this.source.connect(this.worklet);
      this.onEvent({ type: 'client.started', data: {} });
    } catch (error) {
      await this.stop('start_failed');
      throw error;
    }
  }

  async stop(reason = 'user'): Promise<void> {
    const socket = this.socket;
    this.socket = undefined;
    if (socket?.readyState === 1) {
      socket.send(JSON.stringify({ type: 'stream.stop' }));
    }
    this.worklet?.disconnect();
    this.source?.disconnect();
    this.worklet = undefined;
    this.source = undefined;
    this.stream?.getTracks().forEach(track => track.stop());
    this.stream = undefined;
    const context = this.context;
    this.context = undefined;
    if (context && context.state !== 'closed') await context.close();
    socket?.close();
    this.onEvent({ type: 'client.stopped', data: { reason } });
  }

  dispose(): void {
    this.unwatch?.();
    this.unwatch = undefined;
    void this.stop('dispose');
  }

  private socketUrl(sessionId: string): string {
    const secure = globalThis.location?.protocol === 'https:';
    const protocol = secure ? 'wss:' : 'ws:';
    const host = globalThis.location?.host || '127.0.0.1:8765';
    return `${protocol}//${host}/api/v1/realtime/sessions/${encodeURIComponent(sessionId)}`;
  }

  private handleSocketMessage(event: MessageEvent): void {
    try {
      const parsed = JSON.parse(String(event.data)) as RealtimeEvent;
      this.onEvent(parsed);
    } catch {
      this.onEvent({ type: 'pipeline.error', data: { message: 'Invalid realtime event' } });
    }
  }
}

function socketReady(socket: WebSocket): Promise<void> {
  if (socket.readyState === 1) return Promise.resolve();
  return new Promise((resolve, reject) => {
    socket.addEventListener('open', () => resolve(), { once: true });
    socket.addEventListener('error', () => reject(new Error('WebSocket connection failed')), { once: true });
  });
}
