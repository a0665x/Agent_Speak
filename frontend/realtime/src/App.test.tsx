import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import { App } from './App';
import { I18nProvider, type Locale } from './i18n';
import type { ASRModelId, CorrectionModelId, ModelCatalog } from './models';

const realtime = vi.hoisted(() => ({
  checkDevices: vi.fn(),
  start: vi.fn(),
  stop: vi.fn(),
  dispose: vi.fn(),
}));
const resources = vi.hoisted(() => ({
  reset: vi.fn(),
  wait: vi.fn(),
}));

vi.mock('./audio/realtimeClient', () => ({
  RealtimeClient: class {
    checkDevices = realtime.checkDevices;
    start = realtime.start;
    stop = realtime.stop;
    dispose = realtime.dispose;
  },
}));

vi.mock('./resources', async importOriginal => {
  const actual = await importOriginal<typeof import('./resources')>();
  return {
    ...actual,
    resetResource: resources.reset,
    waitForResourceOperation: resources.wait,
  };
});

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  realtime.checkDevices.mockResolvedValue({
    ready: true,
    reason: 'ready',
    input: { deviceId: 'default', label: 'Default Bluetooth microphone', kind: 'audioinput' },
    output: { deviceId: 'default', label: 'Default Bluetooth audio', kind: 'audiooutput' },
  });
  realtime.start.mockResolvedValue(undefined);
  realtime.stop.mockResolvedValue(undefined);
  resources.reset.mockResolvedValue({
    id: 'op_0123456789abcdef',
    action: 'reset',
    target: 'asr',
    phase: 'queued',
    created_at: '2026-07-23T00:00:00Z',
    updated_at: '2026-07-23T00:00:00Z',
    error_code: null,
    operator_hint: null,
  });
  resources.wait.mockImplementation(async (
    _id: string,
    options?: { onPhase?: (phase: string) => void },
  ) => {
    for (const phase of ['draining', 'starting', 'warming', 'ready']) {
      options?.onPhase?.(phase);
    }
    return {
      id: 'op_0123456789abcdef',
      action: 'reset',
      target: 'asr',
      phase: 'ready',
      created_at: '2026-07-23T00:00:00Z',
      updated_at: '2026-07-23T00:00:01Z',
      error_code: null,
      operator_hint: null,
    };
  });
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === '/api/v1/capabilities') {
      return { ok: true, json: async () => ({ providers: [] }) } as Response;
    }
    if (url === '/api/v1/models') {
      return { ok: true, json: async () => modelCatalog() } as Response;
    }
    if (url === '/api/v1/models/active') {
      const selection = JSON.parse(String(init?.body)) as { asr_model: ASRModelId; correction_model: CorrectionModelId };
      return { ok: true, json: async () => modelCatalog(selection.asr_model, selection.correction_model) } as Response;
    }
    const params = new URL(url, 'http://test').searchParams;
    return {
      ok: true,
      json: async () => ({ id: 'session-1', speech_language: params.get('speech_language') }),
    } as Response;
}));
});

function modelCatalog(
  asrModel: ModelCatalog['active']['asr_model'] = 'qwen3-asr-1.7b',
  correctionModel: ModelCatalog['active']['correction_model'] = 'qwen2.5-correction',
): ModelCatalog {
  return {
    asr: [
      { id: 'qwen3-asr-1.7b', label: 'Qwen3-ASR 1.7B', description: 'Multilingual and code-switching.', ready: true },
      { id: 'breeze-asr-25', label: 'Breeze-ASR-25', description: 'Taiwan Mandarin and code-switching.', ready: true },
      { id: 'faster-whisper-small', label: 'Faster Whisper Small', description: 'Lightweight baseline.', ready: true },
    ],
    correction: [
      { id: 'qwen2.5-correction', label: 'Qwen2.5 Correction', description: 'Local correction.', ready: true },
      { id: 'disabled', label: 'Disabled / Raw ASR', description: 'Raw ASR.', ready: true },
    ],
    active: {
      asr_model: asrModel,
      correction_model: correctionModel,
      requested_asr_model: null,
      state: 'ready',
      leased_by: null,
      device: 'cuda',
      error_code: null,
    },
  };
}

function renderApp(locale: Locale = 'en') {
  return render(<I18nProvider initialLocale={locale}><App /></I18nProvider>);
}

test('renders the disabled realtime start control', () => {
  renderApp();
  expect(screen.getByRole('button', { name: /Start realtime listening/ })).toBeDisabled();
  expect(screen.getByRole('heading', { name: 'ASR Realtime Demo' })).toBeInTheDocument();
  expect(screen.getByText('Quickly locate model selection, processing state, and transcript data visualization.')).toBeInTheDocument();
  expect(screen.getByTestId('particle-field')).toHaveAttribute('data-profile', 'subtle');
  expect(screen.getByRole('heading', { name: 'Realtime processing' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'ASR text relationships' })).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(5);
});

test('resets ASR resources and restores the pinned model catalog', async () => {
  renderApp();
  const selector = await screen.findByRole('combobox', {
    name: 'ASR model',
  });

  fireEvent.click(screen.getByRole('button', {
    name: 'Reset ASR resources',
  }));

  await waitFor(() => expect(resources.reset).toHaveBeenCalledWith('asr'));
  expect(resources.wait).toHaveBeenCalledWith(
    'op_0123456789abcdef',
    expect.objectContaining({ onPhase: expect.any(Function) }),
  );
  await waitFor(() => expect(selector).toBeEnabled());
  expect(selector).toHaveValue('qwen3-asr-1.7b');
  expect(within(selector).getAllByRole('option')).toHaveLength(3);
  expect(realtime.checkDevices).not.toHaveBeenCalled();
  expect(realtime.start).not.toHaveBeenCalled();
});

test('confirms and stops an active stream before resetting resources', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  renderApp();
  fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
  await waitFor(() => expect(screen.getByRole('button', {
    name: 'Start realtime listening',
  })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', {
    name: 'Start realtime listening',
  }));
  await waitFor(() => expect(realtime.start).toHaveBeenCalledTimes(1));

  fireEvent.click(screen.getByRole('button', {
    name: 'Reset ASR resources',
  }));

  await waitFor(() => expect(realtime.stop).toHaveBeenCalledWith(
    'resource-reset',
  ));
  expect(confirm).toHaveBeenCalledWith(
    'Listening is active. Stop it and reset ASR resources?',
  );
  expect(realtime.stop.mock.invocationCallOrder[0]).toBeLessThan(
    resources.reset.mock.invocationCallOrder[0],
  );
  expect(realtime.start).toHaveBeenCalledTimes(1);
  confirm.mockRestore();
});

test('keeps pinned choices visible and disabled when the worker is unavailable', async () => {
  const unavailable = modelCatalog(null);
  unavailable.active.state = 'unavailable';
  unavailable.active.device = 'unavailable';
  unavailable.active.error_code = 'asr_worker_unavailable';
  unavailable.asr = unavailable.asr.map(item => ({ ...item, ready: false }));
  vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === '/api/v1/capabilities') {
      return { ok: true, json: async () => ({ providers: [] }) } as Response;
    }
    if (url === '/api/v1/models') {
      return { ok: true, json: async () => unavailable } as Response;
    }
    return { ok: true, json: async () => ({}) } as Response;
  });

  renderApp();

  const selector = await screen.findByRole('combobox', {
    name: 'ASR model',
  });
  expect(within(selector).getAllByRole('option')).toHaveLength(3);
  expect(selector).toBeDisabled();
});

test('switches active models immediately without a submit button', async () => {
  renderApp();
  const asr = await screen.findByRole('combobox', { name: 'ASR model' });
  expect(asr).toHaveValue('qwen3-asr-1.7b');
  expect(screen.getByText('qwen3-asr-1.7b')).toBeInTheDocument();
  expect(screen.getByRole('combobox', { name: 'Correction model' })).toHaveValue('qwen2.5-correction');

  fireEvent.change(asr, { target: { value: 'breeze-asr-25' } });

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/models/active', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asr_model: 'breeze-asr-25', correction_model: 'qwen2.5-correction' }),
  }));
  expect(screen.queryByRole('button', { name: /submit/i })).not.toBeInTheDocument();
});

test('keeps the selected model and worker row synchronized until the new model is ready', async () => {
  let resolveReady!: (catalog: ReturnType<typeof modelCatalog>) => void;
  const readyCatalog = new Promise<ReturnType<typeof modelCatalog>>(resolve => { resolveReady = resolve; });
  let modelReads = 0;
  vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === '/api/v1/capabilities') {
      return { ok: true, json: async () => ({ providers: [] }) } as Response;
    }
    if (url === '/api/v1/models/active') {
      const loading = modelCatalog();
      loading.active.requested_asr_model = 'breeze-asr-25';
      loading.active.state = 'loading';
      return { ok: true, json: async () => loading } as Response;
    }
    if (url === '/api/v1/models') {
      modelReads += 1;
      if (modelReads <= 2) return { ok: true, json: async () => modelCatalog() } as Response;
      return { ok: true, json: async () => readyCatalog } as Response;
    }
    const params = new URL(url, 'http://test').searchParams;
    return {
      ok: true,
      json: async () => ({ id: 'session-1', speech_language: params.get('speech_language') }),
    } as Response;
  });

  renderApp();
  const selector = await screen.findByRole('combobox', { name: 'ASR model' });
  fireEvent.change(selector, { target: { value: 'breeze-asr-25' } });

  await waitFor(() => expect(selector).toBeDisabled());
  const lifecycle = document.querySelector('.model-lifecycle');
  expect(lifecycle).not.toBeNull();
  expect(lifecycle).toHaveAttribute('data-ready', 'false');
  expect(lifecycle).toHaveClass('is-switching');
  expect(lifecycle?.querySelector('.model-spinner')).not.toBeNull();
  const asrRow = screen.getByText('ASR').closest('div');
  expect(asrRow).not.toBeNull();
  expect(within(asrRow!).getByText('breeze-asr-25')).toBeInTheDocument();
  expect(screen.queryByText('Ready')).not.toBeInTheDocument();

  resolveReady(modelCatalog('breeze-asr-25'));
  await waitFor(() => expect(selector).toBeEnabled());
  expect(lifecycle).toHaveAttribute('data-ready', 'true');
  expect(lifecycle).not.toHaveClass('is-switching');
  expect(screen.getAllByText('Ready').length).toBeGreaterThan(0);
  expect(selector).toHaveValue('breeze-asr-25');
  expect(within(asrRow!).getByText('breeze-asr-25')).toBeInTheDocument();
});

test('rolls the selector and worker row back together when model activation fails', async () => {
  vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === '/api/v1/capabilities') {
      return { ok: true, json: async () => ({ providers: [] }) } as Response;
    }
    if (url === '/api/v1/models') {
      return { ok: true, json: async () => modelCatalog() } as Response;
    }
    if (url === '/api/v1/models/active') {
      return { ok: false, json: async () => ({ code: 'model_load_failed' }) } as Response;
    }
    return { ok: true, json: async () => ({ id: 'session-1', speech_language: 'en' }) } as Response;
  });

  renderApp();
  const selector = await screen.findByRole('combobox', { name: 'ASR model' });
  fireEvent.change(selector, { target: { value: 'breeze-asr-25' } });

  await screen.findByRole('alert');
  expect(selector).toHaveValue('qwen3-asr-1.7b');
  const asrRow = screen.getByText('ASR').closest('div');
  expect(asrRow).not.toBeNull();
  expect(within(asrRow!).getByText('qwen3-asr-1.7b')).toBeInTheDocument();
});

test('shows the target model while an active stream is still stopping', async () => {
  let releaseStop!: () => void;
  const stopping = new Promise<void>(resolve => { releaseStop = resolve; });

  renderApp();
  fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start realtime listening' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Start realtime listening' }));
  await waitFor(() => expect(realtime.start).toHaveBeenCalledTimes(1));
  realtime.stop.mockReturnValueOnce(stopping);

  const selector = await screen.findByRole('combobox', { name: 'ASR model' });
  fireEvent.change(selector, { target: { value: 'breeze-asr-25' } });
  await waitFor(() => expect(selector).toBeDisabled());

  try {
    const asrRow = screen.getByText('ASR').closest('div');
    expect(asrRow).not.toBeNull();
    expect(within(asrRow!).getByText('breeze-asr-25')).toBeInTheDocument();
    expect(document.querySelector('.model-lifecycle')).toHaveClass('is-switching');
  } finally {
    releaseStop();
  }
});

test('safely stops and resumes a ready active stream when the ASR model changes', async () => {
  renderApp();
  fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start realtime listening' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Start realtime listening' }));
  await waitFor(() => expect(realtime.start).toHaveBeenCalledTimes(1));

  fireEvent.change(await screen.findByRole('combobox', { name: 'ASR model' }), {
    target: { value: 'breeze-asr-25' },
  });

  await waitFor(() => expect(realtime.stop).toHaveBeenCalledWith('model-switch'));
  await waitFor(() => expect(realtime.start).toHaveBeenCalledTimes(2));
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/sessions?speech_language=en&asr_model=breeze-asr-25&correction_model=qwen2.5-correction',
    { method: 'POST' },
  );
});

test('keeps the first model selection pending until the previous lease is released', async () => {
  let modelReads = 0;
  vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === '/api/v1/capabilities') {
      return { ok: true, json: async () => ({ providers: [] }) } as Response;
    }
    if (url === '/api/v1/models') {
      modelReads += 1;
      const catalog = modelCatalog();
      if (modelReads > 1 && modelReads <= 21) catalog.active.leased_by = 'previous-session';
      return { ok: true, json: async () => catalog } as Response;
    }
    if (url === '/api/v1/models/active') {
      if (modelReads <= 21) return { ok: false, json: async () => ({ code: 'model_lease_conflict' }) } as Response;
      const selection = JSON.parse(String(init?.body)) as { asr_model: ASRModelId; correction_model: CorrectionModelId };
      return { ok: true, json: async () => modelCatalog(selection.asr_model, selection.correction_model) } as Response;
    }
    return { ok: true, json: async () => ({ id: 'session-1', speech_language: 'en' }) } as Response;
  });

  renderApp();
  const selector = await screen.findByRole('combobox', { name: 'ASR model' });
  fireEvent.change(selector, { target: { value: 'breeze-asr-25' } });

  expect(selector).toHaveValue('breeze-asr-25');
  expect(selector).toBeDisabled();
  await waitFor(() => expect(selector).toBeEnabled(), { timeout: 5_000 });
  expect(selector).toHaveValue('breeze-asr-25');
  const asrRow = screen.getByText('ASR').closest('div');
  expect(asrRow).not.toBeNull();
  expect(within(asrRow!).getByText('breeze-asr-25')).toBeInTheDocument();
  expect(screen.getAllByText('Ready').length).toBeGreaterThan(0);
});

test('reduced motion keeps ambient status textual and static', () => {
  render(<I18nProvider initialLocale="en"><App forceReducedMotion /></I18nProvider>);
  expect(screen.getByTestId('particle-field')).toHaveAttribute('data-animated', 'false');
  expect(screen.getByText(/System audio input and output not checked/)).toBeInTheDocument();
});

test('changes the complete realtime surface language from the navigation selector', () => {
  renderApp();
  const selector = screen.getByRole('combobox', { name: 'Language' });
  fireEvent.change(selector, { target: { value: 'ja' } });
  expect(screen.getByRole('heading', { name: 'ASR リアルタイムデモ' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Realtime listening を開始' })).toBeDisabled();
  expect(screen.getByRole('heading', { name: 'ASR テキストの関係' })).toBeInTheDocument();
});

test('speech language follows presentation locale until explicitly overridden', () => {
  renderApp('ja');
  const speech = screen.getByRole('combobox', { name: '音声言語' });
  expect(speech).toHaveValue('ja');

  fireEvent.change(screen.getByRole('combobox', { name: '言語' }), { target: { value: 'ko' } });
  expect(screen.getByRole('combobox', { name: '음성 언어' })).toHaveValue('ko');

  fireEvent.change(screen.getByRole('combobox', { name: '음성 언어' }), { target: { value: 'auto' } });
  fireEvent.change(screen.getByRole('combobox', { name: '언어' }), { target: { value: 'en' } });
  expect(screen.getByRole('combobox', { name: 'Speech language' })).toHaveValue('auto');
});

test('freezes the selected language for an active session and queues later changes', async () => {
  renderApp('en');
  fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start realtime listening' })).toBeEnabled());

  fireEvent.click(screen.getByRole('button', { name: 'Start realtime listening' }));
  await waitFor(() => expect(realtime.start).toHaveBeenCalledWith('session-1'));

  expect(fetch).toHaveBeenCalledWith('/api/v1/sessions?speech_language=en&asr_model=qwen3-asr-1.7b&correction_model=qwen2.5-correction', { method: 'POST' });
  expect(screen.getByText('Locked for this session: English')).toBeInTheDocument();

  fireEvent.change(screen.getByRole('combobox', { name: 'Speech language' }), { target: { value: 'ko' } });
  expect(screen.getByText('Applies to the next session')).toBeInTheDocument();
  expect(screen.getByText('Locked for this session: English')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Stop realtime listening' }));
  await waitFor(() => expect(realtime.stop).toHaveBeenCalled());
  expect(screen.getByText('Locked for this session: English')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Start realtime listening' }));
  await waitFor(() => expect(realtime.start).toHaveBeenCalledTimes(2));
  expect(fetch).toHaveBeenCalledWith('/api/v1/sessions?speech_language=ko&asr_model=qwen3-asr-1.7b&correction_model=qwen2.5-correction', { method: 'POST' });
});
