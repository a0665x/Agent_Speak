import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import { App } from './App';
import { I18nProvider, type Locale } from './i18n';

const realtime = vi.hoisted(() => ({
  checkDevices: vi.fn(),
  start: vi.fn(),
  stop: vi.fn(),
  dispose: vi.fn(),
}));

vi.mock('./audio/realtimeClient', () => ({
  RealtimeClient: class {
    checkDevices = realtime.checkDevices;
    start = realtime.start;
    stop = realtime.stop;
    dispose = realtime.dispose;
  },
}));

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
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === '/api/v1/capabilities') {
      return { ok: true, json: async () => ({ providers: [] }) } as Response;
    }
    if (url === '/api/v1/models') {
      return { ok: true, json: async () => modelCatalog() } as Response;
    }
    if (url === '/api/v1/models/active') {
      const selection = JSON.parse(String(init?.body)) as { asr_model: string; correction_model: string };
      return { ok: true, json: async () => modelCatalog(selection.asr_model, selection.correction_model) } as Response;
    }
    const params = new URL(url, 'http://test').searchParams;
    return {
      ok: true,
      json: async () => ({ id: 'session-1', speech_language: params.get('speech_language') }),
    } as Response;
}));
});

function modelCatalog(asrModel = 'qwen3-asr-1.7b', correctionModel = 'qwen2.5-correction') {
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
  expect(screen.getByRole('heading', { name: /Speak\. See it flow\./ })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Realtime processing' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'ASR text relationships' })).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(5);
});

test('switches active models immediately without a submit button', async () => {
  renderApp();
  const asr = await screen.findByRole('combobox', { name: 'ASR model' });
  expect(asr).toHaveValue('qwen3-asr-1.7b');
  expect(screen.getByRole('combobox', { name: 'Correction model' })).toHaveValue('qwen2.5-correction');

  fireEvent.change(asr, { target: { value: 'breeze-asr-25' } });

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/models/active', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asr_model: 'breeze-asr-25', correction_model: 'qwen2.5-correction' }),
  }));
  expect(screen.queryByRole('button', { name: /submit/i })).not.toBeInTheDocument();
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

test('reduced motion keeps ambient status textual and static', () => {
  render(<I18nProvider initialLocale="en"><App forceReducedMotion /></I18nProvider>);
  expect(screen.getByTestId('ambient-waves')).toHaveAttribute('data-animated', 'false');
  expect(screen.getByText(/System audio input and output not checked/)).toBeInTheDocument();
});

test('changes the complete realtime surface language from the navigation selector', () => {
  renderApp();
  const selector = screen.getByRole('combobox', { name: 'Language' });
  fireEvent.change(selector, { target: { value: 'ja' } });
  expect(screen.getByRole('heading', { name: '話す。流れが見える。' })).toBeInTheDocument();
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
