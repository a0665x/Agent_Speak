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
    input: { deviceId: 'mic', label: 'Zone Vibe 100' } as MediaDeviceInfo,
    output: { deviceId: 'out', label: 'Zone Vibe 100' } as MediaDeviceInfo
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
