import { describe, expect, it, vi } from 'vitest';
import { getCloneStatus, synthesizeSpeech, validateReference } from './api';

describe('TTS clone API client', () => {
  it('posts repeated cues and returns WAV without playing it', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(
      'wav',
      { status: 200, headers: { 'content-type': 'audio/wav' } },
    ));
    const play = vi.fn();

    const result = await synthesizeSpeech({
      text: 'Hello',
      styleCues: ['warm', 'sigh'],
      useClone: true,
      reference: new Blob(['reference'], { type: 'audio/wav' }),
    }, fetcher);

    expect(fetcher).toHaveBeenCalledWith('/api/v1/tts-clone/synthesize', {
      method: 'POST',
      body: expect.any(FormData),
    });
    const body = fetcher.mock.calls[0][1].body as FormData;
    expect(body.getAll('style_cues')).toEqual(['warm', 'sigh']);
    expect(body.get('reference')).toBeInstanceOf(File);
    expect(result.type).toBe('audio/wav');
    expect(play).not.toHaveBeenCalled();
  });

  it('omits the reference when default voice is selected', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(
      'wav',
      { status: 200, headers: { 'content-type': 'audio/wav' } },
    ));

    await synthesizeSpeech({
      text: 'Hello',
      styleCues: [],
      useClone: false,
    }, fetcher);

    const body = fetcher.mock.calls[0][1].body as FormData;
    expect(body.has('reference')).toBe(false);
  });

  it('parses stable error envelopes', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: {
        code: 'wrong_gpu_mode',
        message: 'Switch mode',
        stage: 'tts_clone',
        retryable: false,
        details: { operator_hint: './run.sh --tts-up' },
      },
    }), { status: 409, headers: { 'content-type': 'application/json' } }));

    await expect(getCloneStatus(fetcher)).rejects.toMatchObject({
      code: 'wrong_gpu_mode',
      operatorHint: './run.sh --tts-up',
    });
  });

  it('gets status and validates a transient reference', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        gpu_mode: 'tts',
        accelerator: 'nvidia',
        state: 'ready',
        model: 'voxcpm2',
        device: 'cuda',
        ready: true,
        error_code: null,
        operator_hint: null,
      }), { status: 200, headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        duration_seconds: 10,
        rms: 0.2,
        peak: 0.4,
        voiced_ratio: 0.9,
        quality: 'good',
      }), { status: 200, headers: { 'content-type': 'application/json' } }));

    await expect(getCloneStatus(fetcher)).resolves.toMatchObject({ ready: true });
    await expect(validateReference(
      new Blob(['reference'], { type: 'audio/wav' }),
      fetcher,
    )).resolves.toMatchObject({ quality: 'good' });
    expect(fetcher).toHaveBeenLastCalledWith(
      '/api/v1/tts-clone/reference/validate',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
