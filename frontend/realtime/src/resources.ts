export type ResourceProfile = 'asr_only' | 'tts_only' | 'full_pipeline';
export type ResourceWorkload = 'asr' | 'correction' | 'agent' | 'tts';
export type ResourcePhase =
  | 'queued'
  | 'draining'
  | 'releasing'
  | 'starting'
  | 'warming'
  | 'ready'
  | 'failed'
  | 'rolled_back'
  | 'cancelled';

export type ResourceOperation = {
  id: string;
  action: 'reconcile' | 'reset';
  target: string;
  phase: ResourcePhase;
  created_at: string;
  updated_at: string;
  error_code: string | null;
  operator_hint: string | null;
};

type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

type PollOptions = {
  fetcher?: Fetcher;
  intervalMs?: number;
  timeoutMs?: number;
  onPhase?: (phase: ResourcePhase) => void;
  onReconnect?: () => void;
};

const PHASES = new Set<ResourcePhase>([
  'queued',
  'draining',
  'releasing',
  'starting',
  'warming',
  'ready',
  'failed',
  'rolled_back',
  'cancelled',
]);
const TERMINAL_PHASES = new Set<ResourcePhase>([
  'ready',
  'failed',
  'rolled_back',
  'cancelled',
]);

export class ResourceApiError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    message: string,
    readonly retryable = false,
    readonly operatorHint: string | null = null,
  ) {
    super(message);
    this.name = 'ResourceApiError';
  }
}

function parseOperation(value: unknown): ResourceOperation {
  if (!value || typeof value !== 'object') {
    throw new ResourceApiError(
      'invalid_resource_response',
      502,
      'The resource service returned an invalid response',
      true,
    );
  }
  const item = value as Record<string, unknown>;
  if (
    typeof item.id !== 'string'
    || !/^op_[0-9a-f]{16,32}$/.test(item.id)
    || (item.action !== 'reconcile' && item.action !== 'reset')
    || typeof item.target !== 'string'
    || typeof item.phase !== 'string'
    || !PHASES.has(item.phase as ResourcePhase)
    || typeof item.created_at !== 'string'
    || typeof item.updated_at !== 'string'
    || (item.error_code !== null && typeof item.error_code !== 'string')
    || (item.operator_hint !== null && typeof item.operator_hint !== 'string')
  ) {
    throw new ResourceApiError(
      'invalid_resource_response',
      502,
      'The resource service returned an invalid response',
      true,
    );
  }
  return item as ResourceOperation;
}

async function parseError(response: Response): Promise<ResourceApiError> {
  try {
    const payload = await response.json() as {
      error?: {
        code?: unknown;
        message?: unknown;
        retryable?: unknown;
        details?: { operator_hint?: unknown };
      };
    };
    const error = payload.error;
    if (
      typeof error?.code === 'string'
      && typeof error.message === 'string'
      && typeof error.retryable === 'boolean'
    ) {
      return new ResourceApiError(
        error.code,
        response.status,
        error.message,
        error.retryable,
        typeof error.details?.operator_hint === 'string'
          ? error.details.operator_hint
          : null,
      );
    }
  } catch {
    // Fall through to the privacy-safe transport error.
  }
  return new ResourceApiError(
    'resource_request_failed',
    response.status,
    'The resource request failed',
    response.status >= 500,
  );
}

async function requestOperation(
  path: string,
  init: RequestInit,
  fetcher: Fetcher = fetch,
): Promise<ResourceOperation> {
  const response = await fetcher(path, init);
  if (!response.ok) throw await parseError(response);
  return parseOperation(await response.json());
}

export function reconcileResources(
  profile: ResourceProfile,
): Promise<ResourceOperation> {
  return requestOperation('/api/v1/resources/reconcile', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ profile }),
  });
}

export function resetResource(
  workload: Extract<ResourceWorkload, 'asr' | 'tts'>,
): Promise<ResourceOperation> {
  return requestOperation(`/api/v1/resources/${workload}/reset`, {
    method: 'POST',
  });
}

export function fetchResourceOperation(
  id: string,
  fetcher: Fetcher = fetch,
): Promise<ResourceOperation> {
  return requestOperation(
    `/api/v1/resource-operations/${encodeURIComponent(id)}`,
    { method: 'GET' },
    fetcher,
  );
}

function pause(delayMs: number): Promise<void> {
  return new Promise(resolve => globalThis.setTimeout(resolve, delayMs));
}

export async function waitForResourceOperation(
  id: string,
  options: PollOptions = {},
): Promise<ResourceOperation> {
  const {
    fetcher = fetch,
    intervalMs = 500,
    timeoutMs = 420_000,
    onPhase = () => undefined,
    onReconnect = () => undefined,
  } = options;
  const deadline = Date.now() + timeoutMs;
  let delayMs = intervalMs;

  while (Date.now() < deadline) {
    try {
      const operation = await fetchResourceOperation(id, fetcher);
      onPhase(operation.phase);
      if (TERMINAL_PHASES.has(operation.phase)) return operation;
      delayMs = intervalMs;
    } catch (cause) {
      if (
        cause instanceof ResourceApiError
        && cause.status < 500
      ) {
        throw cause;
      }
      onReconnect();
      delayMs = Math.min(
        2_000,
        Math.max(intervalMs, delayMs * 2),
      );
    }
    await pause(delayMs);
  }
  throw new ResourceApiError(
    'resource_operation_timeout',
    504,
    'Resource operation timed out',
    true,
  );
}
