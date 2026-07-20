import { describe, expect, it, vi } from 'vitest';
import { checkAudioDevices } from './deviceGate';

describe('checkAudioDevices', () => {
  it('stops the temporary permission stream and requires matching input and output', async () => {
    const stop = vi.fn();
    const mediaDevices = {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }),
      enumerateDevices: vi.fn().mockResolvedValue([
        { kind: 'audioinput', deviceId: 'mic', label: 'Zone Vibe 100' },
        { kind: 'audiooutput', deviceId: 'out', label: 'Zone Vibe 100' }
      ])
    } as unknown as MediaDevices;
    const result = await checkAudioDevices(mediaDevices, 'Zone Vibe 100');
    expect(stop).toHaveBeenCalledOnce();
    expect(result.ready).toBe(true);
  });

  it('keeps start disabled when either endpoint is absent', async () => {
    const stop = vi.fn();
    const mediaDevices = {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }),
      enumerateDevices: vi.fn().mockResolvedValue([
        { kind: 'audioinput', deviceId: 'mic', label: 'Zone Vibe 100' }
      ])
    } as unknown as MediaDevices;
    const result = await checkAudioDevices(mediaDevices, 'Zone Vibe 100');
    expect(stop).toHaveBeenCalledOnce();
    expect(result).toMatchObject({ ready: false, reason: 'missing_output' });
  });
});
