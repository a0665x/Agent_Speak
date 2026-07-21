import type { PipelineStage, RealtimeAction, RealtimeEvent } from '../types';

export type TranscriptRow = {
  utteranceId: string;
  text: string;
  status: 'partial' | 'revisable' | 'locked';
};

export type RealtimeState = {
  lastSequence: number;
  stage: PipelineStage;
  stream: 'ready' | 'listening' | 'speech' | 'endpoint' | 'finalizing' | 'correcting' | 'stopped';
  rows: TranscriptRow[];
  completedUtteranceIds: string[];
  asrQueue: number;
  endpointMs: number;
  warning?: string;
};

export const initialState: RealtimeState = {
  lastSequence: 0,
  stage: 'idle',
  stream: 'ready',
  rows: [],
  completedUtteranceIds: [],
  asrQueue: 0,
  endpointMs: 0
};

export function realtimeReducer(state: RealtimeState, event: RealtimeAction): RealtimeState {
  if (!('sequence' in event)) return initialState;
  if (event.sequence <= state.lastSequence) return state;
  let next: RealtimeState = { ...state, lastSequence: event.sequence };
  switch (event.type) {
    case 'stream.started':
      return { ...next, stage: 'listening', stream: 'listening' };
    case 'stream.stopped':
      return { ...next, stage: 'idle', stream: 'stopped', asrQueue: 0 };
    case 'vad.speech_started':
      return { ...next, stage: 'voice', stream: 'speech', endpointMs: 0 };
    case 'endpoint.candidate':
      return { ...next, stage: 'endpoint', stream: 'endpoint', endpointMs: Number(event.data.silence_ms ?? 900) };
    case 'endpoint.extended':
      return { ...next, stage: 'endpoint', stream: 'endpoint', endpointMs: 1800 };
    case 'endpoint.cancelled':
      return { ...next, stage: 'voice', stream: 'speech', endpointMs: 0 };
    case 'asr.queued':
      return {
        ...next,
        stage: event.data.mode === 'final' ? 'correction' : 'asr',
        stream: event.data.mode === 'final' ? 'finalizing' : next.stream,
        asrQueue: next.asrQueue + 1
      };
    case 'asr.processing':
      return {
        ...next,
        stage: event.data.mode === 'final' ? 'correction' : 'asr',
        stream: event.data.mode === 'final' ? 'finalizing' : next.stream
      };
    case 'asr.partial':
      return { ...next, stage: 'asr', asrQueue: Math.max(0, next.asrQueue - 1), rows: upsert(next.rows, event, 'partial') };
    case 'asr.final':
      return { ...next, stage: 'correction', stream: 'correcting', asrQueue: Math.max(0, next.asrQueue - 1), rows: upsert(next.rows, event, 'revisable') };
    case 'correction.processing':
      return { ...next, stage: 'correction', stream: 'correcting' };
    case 'transcript.revised': {
      if (!event.utterance_id) return next;
      const index = next.rows.findIndex(row => row.utteranceId === event.utterance_id);
      if (index < 0) return next;
      const rows = next.rows.map(row => ({ ...row }));
      rows[index] = { ...rows[index], text: String(event.data.current_text ?? rows[index].text), status: 'revisable' };
      if (index > 0) {
        rows[index - 1] = { ...rows[index - 1], text: String(event.data.previous_text ?? rows[index - 1].text), status: 'locked' };
      }
      return { ...next, stage: 'correction', rows };
    }
    case 'utterance.completed': {
      const completedUtteranceIds = event.utterance_id && !next.completedUtteranceIds.includes(event.utterance_id)
        ? [...next.completedUtteranceIds, event.utterance_id]
        : next.completedUtteranceIds;
      return { ...next, stage: 'listening', stream: 'listening', completedUtteranceIds };
    }
    case 'pipeline.warning':
      return { ...next, warning: String(event.data.code ?? 'Pipeline warning') };
    case 'pipeline.error':
      return { ...next, stage: 'error' };
    default:
      return next;
  }
}

function upsert(rows: TranscriptRow[], event: RealtimeEvent, status: TranscriptRow['status']): TranscriptRow[] {
  if (!event.utterance_id) return rows;
  const text = String(event.data.text ?? '');
  const index = rows.findIndex(row => row.utteranceId === event.utterance_id);
  if (index >= 0) return rows.map((row, position) => position === index ? { ...row, text, status } : row);
  return [...rows, { utteranceId: event.utterance_id, text, status }];
}
