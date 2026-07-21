export type RealtimeEvent = {
  sequence: number;
  session_id: string;
  utterance_id: string | null;
  type: string;
  at: string;
  data: Record<string, unknown>;
};

export type PipelineStage = 'idle' | 'listening' | 'voice' | 'asr' | 'endpoint' | 'correction' | 'error';

export type RealtimeAction = RealtimeEvent | { type: 'client.session_reset' };

export type DeviceGateResult = {
  ready: boolean;
  input?: MediaDeviceInfo;
  output?: MediaDeviceInfo;
  reason: 'ready' | 'permission_denied' | 'missing_input' | 'missing_output' | 'unchecked';
};
