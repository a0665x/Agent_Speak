import { expect, test } from 'vitest';
import type { ModelCatalog } from './models';
import { deriveModelPresentation } from './modelPresentation';

function catalog(
  activeAsr: ModelCatalog['active']['asr_model'] = 'qwen3-asr-1.7b',
  state = 'ready',
  requestedAsr: ModelCatalog['active']['requested_asr_model'] = null,
): ModelCatalog {
  return {
    asr: [
      { id: 'qwen3-asr-1.7b', label: 'Qwen3-ASR 1.7B', description: '', ready: true },
      { id: 'breeze-asr-25', label: 'Breeze ASR 25', description: '', ready: true },
      { id: 'faster-whisper-small', label: 'Faster-Whisper Small', description: '', ready: true },
    ],
    correction: [
      { id: 'qwen2.5-correction', label: 'Qwen2.5 Correction', description: '', ready: true },
      { id: 'disabled', label: 'Disabled / Raw ASR', description: '', ready: true },
    ],
    active: {
      asr_model: activeAsr,
      correction_model: 'qwen2.5-correction',
      requested_asr_model: requestedAsr,
      state,
      leased_by: null,
      device: 'cuda',
      error_code: null,
    },
  };
}

test('presents the selected targets while the previous ASR is still active', () => {
  const result = deriveModelPresentation(
    catalog('qwen3-asr-1.7b', 'loading', 'breeze-asr-25'),
    'breeze-asr-25',
    'disabled',
    true,
  );

  expect(result.asrModel).toBe('breeze-asr-25');
  expect(result.correctionModel).toBe('disabled');
  expect(result.device).toBe('cuda');
  expect(result.lifecycle).toBe('loading');
  expect(result.switching).toBe(true);
  expect(result.ready).toBe(false);
});

test('is ready only after runtime active and requested states match the selection', () => {
  expect(deriveModelPresentation(catalog('breeze-asr-25'), 'breeze-asr-25', 'qwen2.5-correction', false).ready).toBe(true);
  expect(deriveModelPresentation(catalog('qwen3-asr-1.7b'), 'breeze-asr-25', 'qwen2.5-correction', false).ready).toBe(false);
  expect(deriveModelPresentation(catalog('breeze-asr-25', 'ready', 'breeze-asr-25'), 'breeze-asr-25', 'qwen2.5-correction', false).ready).toBe(false);
  expect(deriveModelPresentation(catalog('breeze-asr-25'), 'breeze-asr-25', 'qwen2.5-correction', true).ready).toBe(false);
});

test('never presents a failed runtime state as ready after rollback', () => {
  const failed = catalog('qwen3-asr-1.7b', 'failed');
  failed.active.error_code = 'model_load_failed';

  const result = deriveModelPresentation(failed, 'qwen3-asr-1.7b', 'qwen2.5-correction', false);

  expect(result.asrModel).toBe('qwen3-asr-1.7b');
  expect(result.lifecycle).toBe('failed');
  expect(result.ready).toBe(false);
});
