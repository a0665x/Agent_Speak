import type { DeviceGateResult } from '../types';

export async function checkAudioDevices(
  mediaDevices: MediaDevices
): Promise<DeviceGateResult> {
  let permissionStream: MediaStream | undefined;
  try {
    permissionStream = await mediaDevices.getUserMedia({ audio: true, video: false });
    const devices = await mediaDevices.enumerateDevices();
    const select = (kind: MediaDeviceKind) =>
      devices.find(device => device.kind === kind && device.deviceId === 'default')
      ?? devices.find(device => device.kind === kind && device.label.trim().length > 0);
    const input = select('audioinput');
    const output = select('audiooutput');
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
