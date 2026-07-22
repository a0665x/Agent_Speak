import { expect, test } from 'vitest';
import { initialState, realtimeReducer } from './reducer';
import type { RealtimeEvent } from '../types';

function event(type: string, data: Record<string, unknown> = {}, utteranceId: string | null = 'u1', sequence = 1): RealtimeEvent {
  return { sequence, session_id: 's', utterance_id: utteranceId, type, at: '', data };
}

test.each([
  ['stream.started', {}, 'listening'],
  ['vad.speech_started', {}, 'voice'],
  ['asr.partial', { text: '測試' }, 'asr'],
  ['endpoint.candidate', { silence_ms: 900 }, 'endpoint'],
  ['correction.processing', {}, 'correction'],
])('maps %s to the %s semantic stage', (type, data, stage) => {
  const next = realtimeReducer(initialState, event(type, data));
  expect(next.stage).toBe(stage);
});

test('records one completed utterance and resets for a new client session', () => {
  const completed = realtimeReducer(initialState, event('utterance.completed', {}, 'u-1'));
  const duplicate = realtimeReducer(completed, event('utterance.completed', {}, 'u-1', 2));
  expect(duplicate.completedUtteranceIds).toEqual(['u-1']);
  expect(realtimeReducer(duplicate, { type: 'client.session_reset' })).toEqual(initialState);
});

test('model switch preserves completed rows, drops partial text, and resets event ordering', () => {
  const completed = realtimeReducer(
    realtimeReducer(initialState, event('asr.final', { text: 'kept' }, 'u1', 1)),
    event('utterance.completed', {}, 'u1', 2),
  );
  const withPartial = realtimeReducer(completed, event('asr.partial', { text: 'discard me' }, 'u2', 3));

  const switched = realtimeReducer(withPartial, { type: 'client.model_switched' });

  expect(switched.rows.map(row => row.text)).toEqual(['kept']);
  expect(switched.lastSequence).toBe(0);
  expect(realtimeReducer(switched, event('stream.started', {}, null, 1)).stage).toBe('listening');
});

test('ignores duplicate sequence and never mixes utterance partials', () => {
  const one = realtimeReducer(initialState, {
    sequence: 2, session_id: 's', utterance_id: 'u1', type: 'asr.partial', at: '', data: { text: '第一' }
  });
  const duplicate = realtimeReducer(one, {
    sequence: 2, session_id: 's', utterance_id: 'u2', type: 'asr.partial', at: '', data: { text: '錯誤' }
  });
  expect(duplicate).toBe(one);
  const two = realtimeReducer(one, {
    sequence: 3, session_id: 's', utterance_id: 'u2', type: 'asr.partial', at: '', data: { text: '第二' }
  });
  expect(two.rows.find(row => row.utteranceId === 'u1')?.text).toBe('第一');
  expect(two.rows.find(row => row.utteranceId === 'u2')?.text).toBe('第二');
});

test('revision changes only current and immediately previous rows', () => {
  let state = realtimeReducer(initialState, {
    sequence: 1, session_id: 's', utterance_id: 'u1', type: 'asr.final', at: '', data: { text: '第一' }
  });
  state = realtimeReducer(state, {
    sequence: 2, session_id: 's', utterance_id: 'u2', type: 'asr.final', at: '', data: { text: '第二' }
  });
  state = realtimeReducer(state, {
    sequence: 3, session_id: 's', utterance_id: 'u2', type: 'transcript.revised', at: '',
    data: { previous_text: '第一。', current_text: '第二。', changed: true }
  });
  expect(state.rows.map(row => row.text)).toEqual(['第一。', '第二。']);
  expect(state.rows[0].status).toBe('locked');
});
