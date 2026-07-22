import { expect, test, vi } from 'vitest';
import { RealtimeClient } from './realtimeClient';

test('refuses start until the approved device gate is ready', async () => {
  const client = new RealtimeClient();
  await expect(client.start('session')).rejects.toThrow(/device gate/i);
});

test('sends stream.start before PCM and releases every owned resource', async () => {
  const stop = vi.fn();
  const disconnect = vi.fn();
  const closeContext = vi.fn().mockResolvedValue(undefined);
  const sent: unknown[] = [];
  const socket = {
    readyState: 1,
    send: vi.fn((value: unknown) => sent.push(value)),
    close: vi.fn(),
    addEventListener: vi.fn((type: string, callback: () => void) => {
      if (type === 'open') callback();
    })
  };
  const port = { onmessage: null as ((event: MessageEvent) => void) | null };
  const worklet = { port, connect: vi.fn(), disconnect };
  const context = {
    state: 'running',
    audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) },
    createMediaStreamSource: vi.fn(() => ({ connect: vi.fn(), disconnect })),
    close: closeContext
  };
  const mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] })
  } as unknown as MediaDevices;
  const client = new RealtimeClient({
    mediaDevices,
    socketFactory: () => socket as unknown as WebSocket,
    contextFactory: () => context as unknown as AudioContext,
    workletFactory: () => worklet as unknown as AudioWorkletNode
  });
  client.approveForTest({
    ready: true,
    reason: 'ready',
    input: { deviceId: 'default', label: 'Default Bluetooth microphone' } as MediaDeviceInfo,
    output: { deviceId: 'default', label: 'Default Bluetooth audio' } as MediaDeviceInfo
  });

  await client.start('session');
  port.onmessage?.({ data: { type: 'pcm', buffer: new ArrayBuffer(640) } } as MessageEvent);
  expect(JSON.parse(sent[0] as string).type).toBe('stream.start');
  expect(sent[1]).toBeInstanceOf(ArrayBuffer);

  await client.stop('user');
  expect(stop).toHaveBeenCalledOnce();
  expect(disconnect).toHaveBeenCalled();
  expect(closeContext).toHaveBeenCalledOnce();
  expect(socket.close).toHaveBeenCalledOnce();
});

test('devicechange invalidates readiness and stops an active client', async () => {
  let invalidate: (() => void) | undefined;
  const stop = vi.fn();
  const events: string[] = [];
  const mediaDevices = {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }),
    enumerateDevices: vi.fn().mockResolvedValue([
      { kind: 'audioinput', deviceId: 'default', label: 'Default input' },
      { kind: 'audiooutput', deviceId: 'default', label: 'Default output' },
    ]),
    addEventListener: vi.fn((_type: string, callback: () => void) => { invalidate = callback; }),
    removeEventListener: vi.fn(),
  } as unknown as MediaDevices;
  const client = new RealtimeClient({
    mediaDevices,
    onEvent: event => events.push(event.type),
  });

  await client.checkDevices();
  invalidate?.();
  await Promise.resolve();

  expect(events).toContain('device.ready');
  expect(events).toContain('device.invalidated');
  await expect(client.start('session')).rejects.toThrow(/device gate/i);
});
