import { expect, test } from 'vitest';
import { initialState, realtimeReducer } from './reducer';

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
