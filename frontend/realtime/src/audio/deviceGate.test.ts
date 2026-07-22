import { describe, expect, it, vi } from 'vitest';
import { checkAudioDevices } from './deviceGate';

function device(kind: MediaDeviceKind, deviceId: string, label: string): MediaDeviceInfo {
  return { kind, deviceId, label, groupId: '', toJSON: () => ({}) } as MediaDeviceInfo;
}

function mediaDevices(devices: MediaDeviceInfo[], stop = vi.fn()): MediaDevices {
  return {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }),
    enumerateDevices: vi.fn().mockResolvedValue(devices),
  } as unknown as MediaDevices;
}

describe('checkAudioDevices', () => {
  it('prefers browser default input and output without a brand filter', async () => {
    const devices = mediaDevices([
      device('audioinput', 'usb-mic', 'USB microphone'),
      device('audioinput', 'default', 'Default — Bluetooth headset microphone'),
      device('audiooutput', 'default', 'Default — Bluetooth headset audio'),
    ]);

    const result = await checkAudioDevices(devices);

    expect(result.ready).toBe(true);
    expect(result.input?.deviceId).toBe('default');
    expect(result.output?.deviceId).toBe('default');
  });

  it('falls back to the first labeled endpoint of each kind', async () => {
    const devices = mediaDevices([
      device('audioinput', 'hidden', ''),
      device('audioinput', 'mic', 'Built-in microphone'),
      device('audioinput', 'usb', 'USB microphone'),
      device('audiooutput', 'speaker', 'System speakers'),
    ]);

    const result = await checkAudioDevices(devices);

    expect(result.input?.deviceId).toBe('mic');
    expect(result.output?.deviceId).toBe('speaker');
  });

  it.each([
    [[device('audiooutput', 'out', 'Output')], 'missing_input'],
    [[device('audioinput', 'mic', 'Input')], 'missing_output'],
  ] as const)('keeps start disabled when an endpoint is absent', async (listed, reason) => {
    const result = await checkAudioDevices(mediaDevices([...listed]));
    expect(result).toMatchObject({ ready: false, reason });
  });

  it('stops every temporary permission track after enumeration', async () => {
    const first = vi.fn();
    const second = vi.fn();
    const devices = {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: first }, { stop: second }] }),
      enumerateDevices: vi.fn().mockResolvedValue([
        device('audioinput', 'default', 'Default input'),
        device('audiooutput', 'default', 'Default output'),
      ]),
    } as unknown as MediaDevices;

    await checkAudioDevices(devices);

    expect(first).toHaveBeenCalledOnce();
    expect(second).toHaveBeenCalledOnce();
  });

  it('reports permission denial without leaking the browser error', async () => {
    const devices = {
      getUserMedia: vi.fn().mockRejectedValue(new DOMException('private detail', 'NotAllowedError')),
      enumerateDevices: vi.fn(),
    } as unknown as MediaDevices;

    await expect(checkAudioDevices(devices)).resolves.toEqual({
      ready: false,
      reason: 'permission_denied',
    });
    expect(devices.enumerateDevices).not.toHaveBeenCalled();
  });
});
