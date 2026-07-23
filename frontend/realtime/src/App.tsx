import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { ArrowLeft, CircleStop, Headphones, ShieldCheck } from 'lucide-react';
import { RealtimeClient } from './audio/realtimeClient';
import { AudioStage } from './components/AudioStage';
import { ActiveModels } from './components/ActiveModels';
import { DeviceGate } from './components/DeviceGate';
import { ProcessCycle } from './components/ProcessCycle';
import { SpeechLanguageControl } from './components/SpeechLanguageControl';
import { TranscriptPanel } from './components/TranscriptPanel';
import { UtteranceGraph } from './components/UtteranceGraph';
import { initialState, realtimeReducer } from './state/reducer';
import type { DeviceGateResult, RealtimeEvent } from './types';
import {
  activateModels,
  fetchModelCatalog,
  type ASRModelId,
  type CorrectionModelId,
  type ModelCatalog,
} from './models';
import { deriveModelPresentation, type ModelLifecycle } from './modelPresentation';
import { SUPPORTED_LOCALES, useI18n, type Locale } from './i18n';
import { ParticleField } from './components/ParticleField';
import { ResourceReset } from './components/ResourceReset';
import {
  ResourceApiError,
  resetResource,
  waitForResourceOperation,
  type ResourcePhase,
} from './resources';
import {
  defaultSpeechLanguage,
  readSpeechLanguage,
  writeSpeechLanguage,
  type SpeechLanguage,
} from './speechLanguage';

export type AppProps = { forceReducedMotion?: boolean };

type InferenceDetails = {
  vad: string;
  asr: string;
  asrDevice: string;
  correction: string;
  correctionDevice: string;
};

export function App({ forceReducedMotion = false }: AppProps) {
  const { locale, setLocale, t, href } = useI18n();
  const [state, dispatch] = useReducer(realtimeReducer, initialState);
  const [gate, setGate] = useState<DeviceGateResult>({ ready: false, reason: 'unchecked' });
  const [envelope, setEnvelope] = useState<number[]>([]);
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const initialSpeechLanguage = useMemo(() => readSpeechLanguage(locale), []);
  const [pendingSpeechLanguage, setPendingSpeechLanguage] = useState<SpeechLanguage>(initialSpeechLanguage.value);
  const [speechLanguageOverridden, setSpeechLanguageOverridden] = useState(initialSpeechLanguage.overridden);
  const [lockedSpeechLanguage, setLockedSpeechLanguage] = useState<SpeechLanguage | null>(null);
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog | null>(null);
  const [asrModel, setAsrModel] = useState<ASRModelId>('qwen3-asr-1.7b');
  const [correctionModel, setCorrectionModel] = useState<CorrectionModelId>('qwen2.5-correction');
  const [switchingModels, setSwitchingModels] = useState(false);
  const [resourceBusy, setResourceBusy] = useState(false);
  const [resourcePhase, setResourcePhase] = useState<ResourcePhase | null>(null);
  const [resourceError, setResourceError] = useState('');
  const [resourceHint, setResourceHint] = useState<string | null>(null);
  const [inference, setInference] = useState<InferenceDetails>({
    vad: 'unknown', asr: 'unknown', asrDevice: 'unknown', correction: 'unknown', correctionDevice: 'unknown'
  });
  const clientRef = useRef<RealtimeClient | null>(null);
  const reducedMotion = useMemo(
    () => forceReducedMotion || globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true,
    [forceReducedMotion]
  );
  const modelPresentation = useMemo(
    () => modelCatalog ? deriveModelPresentation(modelCatalog, asrModel, correctionModel, switchingModels) : null,
    [modelCatalog, asrModel, correctionModel, switchingModels],
  );
  const modelStateLabels: Record<ModelLifecycle, string> = {
    ready: t('models.state.ready'), loading: t('models.state.loading'), warming: t('models.state.warming'),
    unloading: t('models.state.unloading'), rollback: t('models.state.rollback'), failed: t('models.state.failed'),
    idle: t('models.state.idle'), unavailable: t('models.state.unavailable'),
  };
  const modelStatusText = modelPresentation
    ? (modelPresentation.switching ? t('models.switching') : modelStateLabels[modelPresentation.lifecycle])
    : '';
  const resourcePhaseLabels: Record<ResourcePhase, string> = {
    queued: t('resources.phase.queued'),
    draining: t('resources.phase.draining'),
    releasing: t('resources.phase.releasing'),
    starting: t('resources.phase.starting'),
    warming: t('resources.phase.warming'),
    ready: t('resources.success'),
    failed: t('resources.phase.failed'),
    rolled_back: t('resources.phase.rolledBack'),
    cancelled: t('resources.phase.cancelled'),
  };

  const refreshCapabilities = async () => {
    const response = await fetch('/api/v1/capabilities');
    if (!response.ok) throw new Error(t('resources.failed'));
    const payload = await response.json();
    const providers = payload.providers as Array<{ stage: string; name: string; device: string }>;
    const provider = (stage: string) => providers.find(item => item.stage === stage);
    setInference({
      vad: provider('vad')?.name ?? 'unknown',
      asr: provider('asr')?.name ?? 'unknown',
      asrDevice: provider('asr')?.device ?? 'unknown',
      correction: provider('correction')?.name ?? 'unknown',
      correctionDevice: provider('correction')?.device ?? 'unknown'
    });
  };

  useEffect(() => {
    const client = new RealtimeClient({ onEvent: event => {
      if ('sequence' in event) dispatch(event as RealtimeEvent);
      if (event.type === 'audio.envelope') setEnvelope((event.data.samples as number[]) ?? []);
      if (event.type === 'device.invalidated') {
        setGate({ ready: false, reason: 'unchecked' });
        setActive(false);
      }
      if (event.type === 'pipeline.error') setError(String(event.data.message ?? 'Realtime pipeline error'));
    } });
    clientRef.current = client;
    void refreshCapabilities().catch(() => undefined);
    void fetchModelCatalog().then(catalog => {
      setModelCatalog(catalog);
      setAsrModel(catalog.active.requested_asr_model ?? catalog.active.asr_model ?? 'qwen3-asr-1.7b');
      setCorrectionModel(catalog.active.correction_model);
    }).catch(() => undefined);
    return () => client.dispose();
  }, []);

  useEffect(() => {
    if (!speechLanguageOverridden) setPendingSpeechLanguage(defaultSpeechLanguage(locale));
  }, [locale, speechLanguageOverridden]);

  const changeSpeechLanguage = (value: SpeechLanguage) => {
    setPendingSpeechLanguage(value);
    setSpeechLanguageOverridden(true);
    writeSpeechLanguage(value);
  };

  const checkDevices = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await clientRef.current!.checkDevices();
      setGate(result);
    } catch (cause) {
      setGate({ ready: false, reason: 'unchecked' });
      setError(cause instanceof Error ? cause.message : t('error.deviceCheck'));
    } finally {
      setBusy(false);
    }
  };

  const createAndStart = async (
    resetTranscript: boolean,
    selectedAsr: ASRModelId = asrModel,
    selectedCorrection: CorrectionModelId = correctionModel,
  ) => {
    if (resetTranscript) dispatch({ type: 'client.session_reset' });
    try {
      const query = new URLSearchParams({
        speech_language: pendingSpeechLanguage,
        asr_model: selectedAsr,
        correction_model: selectedCorrection,
      });
      const response = await fetch(`/api/v1/sessions?${query.toString()}`, { method: 'POST' });
      if (!response.ok) throw new Error(t('error.createSession'));
      const session = await response.json() as { id: string; speech_language: SpeechLanguage };
      setSessionId(session.id);
      setLockedSpeechLanguage(session.speech_language);
      await clientRef.current!.start(session.id);
      setActive(true);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t('error.start'));
      return false;
    }
  };

  const start = async () => {
    setBusy(true);
    setError('');
    await createAndStart(true);
    setBusy(false);
  };

  const stop = async () => {
    setBusy(true);
    try {
      await clientRef.current?.stop('user');
      setActive(false);
    } finally {
      setBusy(false);
    }
  };

  const changeModels = async (nextAsr: ASRModelId, nextCorrection: CorrectionModelId) => {
    if (switchingModels || resourceBusy || (nextAsr === asrModel && nextCorrection === correctionModel)) return;
    const resume = active && gate.ready;
    const previousAsr = asrModel;
    const previousCorrection = correctionModel;
    setSwitchingModels(true);
    setBusy(true);
    setError('');
    setAsrModel(nextAsr);
    setCorrectionModel(nextCorrection);
    try {
      if (active) {
        await clientRef.current?.stop('model-switch');
        setActive(false);
      }
      dispatch({ type: 'client.model_switched' });
      for (let attempt = 0; attempt < 120; attempt += 1) {
        const released = await fetchModelCatalog();
        setModelCatalog(released);
        if (!released.active.leased_by) break;
        await new Promise(resolve => globalThis.setTimeout(resolve, 100));
      }
      let catalog = await activateModels(nextAsr, nextCorrection);
      setModelCatalog(catalog);
      for (let attempt = 0; catalog.active.state !== 'ready' && attempt < 120; attempt += 1) {
        await new Promise(resolve => globalThis.setTimeout(resolve, 500));
        catalog = await fetchModelCatalog();
        setModelCatalog(catalog);
        if (catalog.active.state === 'failed' || catalog.active.state === 'unavailable') break;
      }
      if (catalog.active.state !== 'ready' || catalog.active.asr_model !== nextAsr) {
        throw new Error(catalog.active.error_code ?? t('error.modelSwitch'));
      }
      if (resume) await createAndStart(false, nextAsr, nextCorrection);
    } catch (cause) {
      let rollbackAsr = previousAsr;
      let rollbackCorrection = previousCorrection;
      try {
        const confirmed = await fetchModelCatalog();
        setModelCatalog(confirmed);
        rollbackAsr = confirmed.active.asr_model ?? rollbackAsr;
        rollbackCorrection = confirmed.active.correction_model;
      } catch { /* Preserve the last confirmed local selection. */ }
      setAsrModel(rollbackAsr);
      setCorrectionModel(rollbackCorrection);
      setError(cause instanceof Error ? cause.message : t('error.modelSwitch'));
    } finally {
      setSwitchingModels(false);
      setBusy(false);
    }
  };

  const resetResources = async () => {
    if (resourceBusy) return;
    setResourceBusy(true);
    setResourceError('');
    setResourceHint(null);
    try {
      if (active) {
        await clientRef.current?.stop('resource-reset');
        setActive(false);
      }
      dispatch({ type: 'client.model_switched' });
      const accepted = await resetResource('asr');
      setResourcePhase(accepted.phase);
      const result = await waitForResourceOperation(accepted.id, {
        onPhase: phase => {
          setResourcePhase(phase);
          setResourceError('');
        },
        onReconnect: () => setResourceError(t('resources.reconnecting')),
      });
      if (result.phase !== 'ready') {
        setResourceHint(result.operator_hint);
        throw new ResourceApiError(
          result.error_code ?? 'resource_operation_failed',
          503,
          t('resources.failed'),
          true,
          result.operator_hint,
        );
      }
      const catalog = await fetchModelCatalog();
      setModelCatalog(catalog);
      setAsrModel(catalog.active.requested_asr_model ?? catalog.active.asr_model ?? 'qwen3-asr-1.7b');
      setCorrectionModel(catalog.active.correction_model);
      await refreshCapabilities();
    } catch (cause) {
      if (cause instanceof ResourceApiError) {
        setResourceHint(cause.operatorHint);
      }
      setResourceError(t('resources.failed'));
    } finally {
      setResourceBusy(false);
    }
  };

  return (
    <>
      <a className="skip-link" href="#studio-main">{t('skip')}</a>
      <ParticleField profile="subtle" reducedMotion={reducedMotion} />
      <div className="background-word background-word-top" aria-hidden="true">VOICE · SIGNAL · TEXT</div>
      <div className="background-word background-word-bottom" aria-hidden="true">LISTEN</div>
      <main id="studio-main" className="studio-shell">
        <nav className="studio-nav" aria-label={t('nav.aria')}>
          <a href={href('/')}><ArrowLeft aria-hidden="true" /> {t('nav.projectHome')}</a>
          <div className="studio-nav-tools">
            <span>ASR REALTIME · LOCAL</span>
            <label className="sr-only" htmlFor="language-select">{t('language.label')}</label>
            <select
              id="language-select"
              aria-label={t('language.label')}
              value={locale}
              onChange={event => setLocale(event.target.value as Locale)}
            >
              {SUPPORTED_LOCALES.map(value => <option value={value} key={value}>{languageName(value)}</option>)}
            </select>
          </div>
        </nav>

        <header className="studio-header">
          <div>
            <p className="eyebrow">{t('hero.eyebrow')}</p>
            <h1 aria-label={t('hero.title')}>{t('hero.titleLead')}<br /><span>{t('hero.titleAccent')}</span></h1>
            <p className="lede">{t('hero.lede')}</p>
          </div>
          <div className="session-chip" aria-label={t('session.aria', { value: sessionId || t('session.notStarted') })}>
            <span>{t('session.label')}</span><code>{sessionId || t('session.notStarted')}</code>
          </div>
        </header>

        {error && <div className="error-banner" role="alert"><strong>{error}</strong><span>{t('error.retry')}</span></div>}
        {state.warning && <div className="warning-banner" role="status">{t('warning.pipeline', { value: state.warning })}</div>}

        <section className={`control-deck${gate.ready ? ' ready' : ''}`} aria-label={t('controls.aria')}>
          <DeviceGate gate={gate} />
          <SpeechLanguageControl
            value={pendingSpeechLanguage}
            locked={lockedSpeechLanguage}
            active={active}
            onChange={changeSpeechLanguage}
          />
          <div className="actions">
            <button className="secondary-button" type="button" onClick={checkDevices} disabled={busy || resourceBusy || active}>
              <ShieldCheck aria-hidden="true" /> {busy && !active ? t('controls.checking') : t('controls.checkDevices')}
            </button>
            {!active ? (
              <button className="primary-button" type="button" onClick={start} disabled={!gate.ready || busy || resourceBusy} aria-label={t('controls.startAria')}>
                <Headphones aria-hidden="true" /> {t('controls.start')}
              </button>
            ) : (
              <button className="stop-button" type="button" onClick={stop} disabled={busy} aria-label={t('controls.stopAria')}>
                <CircleStop aria-hidden="true" /> {t('controls.stop')}
              </button>
            )}
          </div>
        </section>

        <ProcessCycle stage={state.stage} reducedMotion={reducedMotion} />

        <div className="live-grid">
          <AudioStage samples={envelope} state={state.stream} />
          <section className="worker-card" aria-label={t('models.aria')}>
            <div><p className="eyebrow">{t('models.eyebrow')}</p><span className={`worker-state${active ? ' live' : ''}`}>{active ? t('models.streaming') : t('models.standby')}</span></div>
            <ResourceReset
              label={t('resources.reset')}
              phase={resourcePhase}
              busy={resourceBusy}
              confirmReset={() => !active || window.confirm(t('resources.confirmActive'))}
              onReset={resetResources}
              phaseLabel={phase => resourcePhaseLabels[phase]}
              error={resourceError}
              recoveryHint={resourceHint}
              reducedMotion={reducedMotion}
            />
            {modelCatalog && modelPresentation && (
              <ActiveModels
                catalog={modelCatalog}
                asrModel={asrModel}
                correctionModel={correctionModel}
                switching={switchingModels}
                disabled={resourceBusy}
                presentation={modelPresentation}
                statusText={modelStatusText}
                onChange={changeModels}
              />
            )}
            <dl>
              <div><dt>VAD</dt><dd>{inference.vad}</dd></div>
              <div>
                <dt>ASR</dt>
                <dd>
                  {modelPresentation?.asrModel ?? inference.asr}
                  <ModelDetailStatus
                    switching={modelPresentation?.switching ?? false}
                    status={modelStatusText}
                    device={modelPresentation?.device ?? inference.asrDevice}
                  />
                </dd>
              </div>
              <div>
                <dt>{t('models.correction')}</dt>
                <dd>
                  {modelPresentation?.correctionModel ?? inference.correction}
                  <ModelDetailStatus
                    switching={modelPresentation?.switching ?? false}
                    status={modelStatusText}
                    device={inference.correctionDevice}
                  />
                </dd>
              </div>
              <div><dt>{t('models.endpoint')}</dt><dd>{state.endpointMs || 900} ms<small>{t('models.hard', { value: 1800 })}</small></dd></div>
              <div><dt>{t('models.queue')}</dt><dd>{t('models.pending', { value: state.asrQueue })}</dd></div>
            </dl>
          </section>
        </div>

        <TranscriptPanel rows={state.rows} />
        <UtteranceGraph rows={state.rows} completedUtteranceIds={state.completedUtteranceIds} />
        <p className="sr-status" aria-live="polite">{gate.ready ? t('sr.devicesReady') : t('sr.devicesNotReady')}; {state.stage}</p>
      </main>
    </>
  );
}

function ModelDetailStatus({ switching, status, device }: { switching: boolean; status: string; device: string }) {
  return (
    <small className={`model-detail-status${switching ? ' is-switching' : ''}`}>
      {switching && <span className="model-spinner" aria-hidden="true" />}
      <span>{status}</span>{status && ' · '}{device}
    </small>
  );
}

function languageName(locale: Locale): string {
  return ({ en: 'English', 'zh-TW': '繁體中文', ja: '日本語', ko: '한국어' })[locale];
}
