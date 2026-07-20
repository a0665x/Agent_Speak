import type { DeviceGateResult } from '../types';

export async function checkAudioDevices(
  mediaDevices: MediaDevices,
  expectedLabel: string
): Promise<DeviceGateResult> {
  let permissionStream: MediaStream | undefined;
  try {
    permissionStream = await mediaDevices.getUserMedia({ audio: true, video: false });
    const devices = await mediaDevices.enumerateDevices();
    const expected = expectedLabel.toLocaleLowerCase();
    const input = devices.find(
      device => device.kind === 'audioinput' && device.label.toLocaleLowerCase().includes(expected)
    );
    const output = devices.find(
      device => device.kind === 'audiooutput' && device.label.toLocaleLowerCase().includes(expected)
    );
    if (!input) return { ready: false, output, reason: 'missing_input' };
    if (!output) return { ready: false, input, reason: 'missing_output' };
    return { ready: true, input, output, reason: 'ready' };
  } catch {
    return { ready: false, reason: 'permission_denied' };
  } finally {
    permissionStream?.getTracks().forEach(track => track.stop());
  }
}

export function watchDeviceChanges(mediaDevices: MediaDevices, invalidate: () => void): () => void {
  mediaDevices.addEventListener('devicechange', invalidate);
  return () => mediaDevices.removeEventListener('devicechange', invalidate);
}
