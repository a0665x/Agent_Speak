import type { RealtimeEvent } from '../types';

export type TranscriptRow = {
  utteranceId: string;
  text: string;
  status: 'partial' | 'revisable' | 'locked';
};

export type RealtimeState = {
  lastSequence: number;
  stream: 'ready' | 'listening' | 'speech' | 'endpoint' | 'finalizing' | 'correcting' | 'stopped';
  rows: TranscriptRow[];
  asrQueue: number;
  endpointMs: number;
  warning?: string;
};

export const initialState: RealtimeState = {
  lastSequence: 0,
  stream: 'ready',
  rows: [],
  asrQueue: 0,
  endpointMs: 0
};

export function realtimeReducer(state: RealtimeState, event: RealtimeEvent): RealtimeState {
  if (event.sequence <= state.lastSequence) return state;
  let next: RealtimeState = { ...state, lastSequence: event.sequence };
  switch (event.type) {
    case 'stream.started':
      return { ...next, stream: 'listening' };
    case 'stream.stopped':
      return { ...next, stream: 'stopped', asrQueue: 0 };
    case 'vad.speech_started':
      return { ...next, stream: 'speech', endpointMs: 0 };
    case 'endpoint.candidate':
      return { ...next, stream: 'endpoint', endpointMs: Number(event.data.silence_ms ?? 900) };
    case 'endpoint.extended':
      return { ...next, stream: 'endpoint', endpointMs: 1800 };
    case 'asr.queued':
      return { ...next, stream: event.data.mode === 'final' ? 'finalizing' : next.stream, asrQueue: next.asrQueue + 1 };
    case 'asr.partial':
      return { ...next, asrQueue: Math.max(0, next.asrQueue - 1), rows: upsert(next.rows, event, 'partial') };
    case 'asr.final':
      return { ...next, stream: 'correcting', asrQueue: Math.max(0, next.asrQueue - 1), rows: upsert(next.rows, event, 'revisable') };
    case 'transcript.revised': {
      if (!event.utterance_id) return next;
      const index = next.rows.findIndex(row => row.utteranceId === event.utterance_id);
      if (index < 0) return next;
      const rows = next.rows.map(row => ({ ...row }));
      rows[index] = { ...rows[index], text: String(event.data.current_text ?? rows[index].text), status: 'revisable' };
      if (index > 0) {
        rows[index - 1] = { ...rows[index - 1], text: String(event.data.previous_text ?? rows[index - 1].text), status: 'locked' };
      }
      return { ...next, rows };
    }
    case 'utterance.completed':
      return { ...next, stream: 'listening' };
    case 'pipeline.warning':
      return { ...next, warning: String(event.data.code ?? 'Pipeline warning') };
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
