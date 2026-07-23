import { afterEach, describe, expect, test, vi } from 'vitest';
import {
  ResourceApiError,
  reconcileResources,
  resetResource,
  waitForResourceOperation,
} from './resources';

function response(
  body: object,
  status = 200,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function operation(phase: string) {
  return {
    id: 'op_0123456789abcdef',
    action: 'reset',
    target: 'asr',
    phase,
    created_at: '2026-07-23T00:00:00Z',
    updated_at: '2026-07-23T00:00:01Z',
    error_code: null,
    operator_hint: null,
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('resource API', () => {
  test('posts fixed reconcile and reset requests', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response(operation('queued'), 202))
      .mockResolvedValueOnce(response(operation('queued'), 202));
    vi.stubGlobal('fetch', fetcher);

    await reconcileResources('asr_only');
    await resetResource('tts');

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      '/api/v1/resources/reconcile',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ profile: 'asr_only' }),
      },
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      '/api/v1/resources/tts/reset',
      { method: 'POST' },
    );
  });

  test('preserves stable API errors and recovery hints', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      error: {
        code: 'tts_resource_not_ready',
        message: 'TTS resources are still warming',
        stage: 'resources',
        retryable: true,
        details: { operator_hint: './run.sh --logs tts-worker' },
      },
    }, 503)));

    await expect(resetResource('tts')).rejects.toMatchObject({
      code: 'tts_resource_not_ready',
      status: 503,
      retryable: true,
      operatorHint: './run.sh --logs tts-worker',
    });
  });

  test('retries temporary gateway loss until ready', async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn()
      .mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValueOnce(response(operation('warming')))
      .mockResolvedValueOnce(response(operation('ready')));
    const phases: string[] = [];

    const resultPromise = waitForResourceOperation(
      'op_0123456789abcdef',
      {
        fetcher,
        intervalMs: 100,
        timeoutMs: 1_000,
        onPhase: phase => phases.push(phase),
      },
    );
    await vi.advanceTimersByTimeAsync(400);

    await expect(resultPromise).resolves.toMatchObject({ phase: 'ready' });
    expect(phases).toEqual(['warming', 'ready']);
  });

  test.each(['failed', 'rolled_back', 'cancelled'])(
    'returns terminal %s operations',
    async phase => {
      const fetcher = vi.fn().mockResolvedValue(response(operation(phase)));

      await expect(waitForResourceOperation(
        'op_0123456789abcdef',
        { fetcher, intervalMs: 1 },
      )).resolves.toMatchObject({ phase });
    },
  );

  test('fails fast for typed 4xx and times out bounded retries', async () => {
    const invalid = vi.fn().mockResolvedValue(response({
      error: {
        code: 'validation_error',
        message: 'Request validation failed',
        stage: 'resources',
        retryable: false,
        details: {},
      },
    }, 422));
    await expect(waitForResourceOperation(
      'op_0123456789abcdef',
      { fetcher: invalid, intervalMs: 1, timeoutMs: 20 },
    )).rejects.toBeInstanceOf(ResourceApiError);
    expect(invalid).toHaveBeenCalledTimes(1);

    vi.useFakeTimers();
    const unavailable = vi.fn().mockRejectedValue(new TypeError('offline'));
    const timed = waitForResourceOperation(
      'op_0123456789abcdef',
      { fetcher: unavailable, intervalMs: 10, timeoutMs: 25 },
    );
    const assertion = expect(timed).rejects.toMatchObject({
      code: 'resource_operation_timeout',
      status: 504,
    });
    await vi.advanceTimersByTimeAsync(100);
    await assertion;
  });
});
