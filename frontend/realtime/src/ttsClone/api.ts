import type {
  CloneStatus,
  ReferenceAssessment,
  SynthesisRequest,
} from './types';
export {
  resetResource,
  waitForResourceOperation,
} from '../resources';

type Fetcher = typeof fetch;

export class CloneApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly retryable = false,
    readonly operatorHint?: string,
  ) {
    super(message);
    this.name = 'CloneApiError';
  }
}

async function ensureSuccess(response: Response): Promise<Response> {
  if (response.ok) return response;
  try {
    const payload = await response.json() as {
      error?: {
        code?: string;
        message?: string;
        retryable?: boolean;
        details?: { operator_hint?: string };
      };
    };
    throw new CloneApiError(
      payload.error?.code ?? 'request_failed',
      payload.error?.message ?? 'Request failed',
      payload.error?.retryable ?? false,
      payload.error?.details?.operator_hint,
    );
  } catch (error) {
    if (error instanceof CloneApiError) throw error;
    throw new CloneApiError('request_failed', `Request failed (${response.status})`);
  }
}

export async function getCloneStatus(
  fetcher: Fetcher = fetch,
): Promise<CloneStatus> {
  const response = await ensureSuccess(await fetcher('/api/v1/tts-clone/status', {
    headers: { accept: 'application/json' },
  }));
  const value = await response.json() as {
    gpu_mode: 'asr' | 'tts';
    accelerator: 'cpu' | 'nvidia';
    resource_policy?: CloneStatus['resourcePolicy'];
    state: CloneStatus['state'];
    model: 'voxcpm2';
    device: string;
    ready: boolean;
    error_code: string | null;
    operator_hint: string | null;
  };
  return {
    gpuMode: value.gpu_mode,
    accelerator: value.accelerator,
    resourcePolicy: value.resource_policy,
    state: value.state,
    model: value.model,
    device: value.device,
    ready: value.ready,
    errorCode: value.error_code ?? undefined,
    operatorHint: value.operator_hint ?? undefined,
  };
}

export async function validateReference(
  reference: Blob,
  fetcher: Fetcher = fetch,
): Promise<ReferenceAssessment> {
  const response = await ensureSuccess(await fetcher(
    '/api/v1/tts-clone/reference/validate',
    {
      method: 'POST',
      headers: { 'content-type': 'audio/wav', accept: 'application/json' },
      body: reference,
    },
  ));
  const value = await response.json() as {
    duration_seconds: number;
    rms: number;
    peak: number;
    voiced_ratio: number;
    quality: ReferenceAssessment['quality'];
  };
  return {
    durationSeconds: value.duration_seconds,
    rms: value.rms,
    peak: value.peak,
    voicedRatio: value.voiced_ratio,
    quality: value.quality,
  };
}

export async function synthesizeSpeech(
  request: SynthesisRequest,
  fetcher: Fetcher = fetch,
): Promise<Blob> {
  const form = new FormData();
  form.append('text', request.text);
  request.styleCues.forEach(cue => form.append('style_cues', cue));
  form.append('use_clone', String(request.useClone));
  if (request.useClone && request.reference) {
    form.append('reference', request.reference, 'reference.wav');
  }
  const response = await ensureSuccess(await fetcher(
    '/api/v1/tts-clone/synthesize',
    { method: 'POST', body: form },
  ));
  const contentType = response.headers.get('content-type')?.split(';', 1)[0];
  if (contentType !== 'audio/wav') {
    throw new CloneApiError(
      'invalid_tts_audio',
      'Speech service returned an unsupported audio type',
    );
  }
  return response.blob();
}
