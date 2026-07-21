import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { ArrowLeft, CircleStop, Headphones, ShieldCheck } from 'lucide-react';
import { RealtimeClient } from './audio/realtimeClient';
import { AudioStage } from './components/AudioStage';
import { DeviceGate } from './components/DeviceGate';
import { ProcessCycle } from './components/ProcessCycle';
import { TranscriptPanel } from './components/TranscriptPanel';
import { UtteranceGraph } from './components/UtteranceGraph';
import { initialState, realtimeReducer } from './state/reducer';
import type { DeviceGateResult, RealtimeEvent } from './types';
import { Waves } from './vendor/reactbits/Waves';

export type AppProps = { forceReducedMotion?: boolean };

type InferenceDetails = {
  vad: string;
  asr: string;
  asrDevice: string;
  correction: string;
  correctionDevice: string;
};

export function App({ forceReducedMotion = false }: AppProps) {
  const [state, dispatch] = useReducer(realtimeReducer, initialState);
  const [gate, setGate] = useState<DeviceGateResult>({ ready: false, reason: 'unchecked' });
  const [envelope, setEnvelope] = useState<number[]>([]);
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [inference, setInference] = useState<InferenceDetails>({
    vad: 'unknown', asr: 'unknown', asrDevice: 'unknown', correction: 'unknown', correctionDevice: 'unknown'
  });
  const clientRef = useRef<RealtimeClient | null>(null);
  const reducedMotion = useMemo(
    () => forceReducedMotion || globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true,
    [forceReducedMotion]
  );

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
    void fetch('/api/v1/capabilities').then(response => response.json()).then(payload => {
      const providers = payload.providers as Array<{ stage: string; name: string; device: string }>;
      const provider = (stage: string) => providers.find(item => item.stage === stage);
      setInference({
        vad: provider('vad')?.name ?? 'unknown',
        asr: provider('asr')?.name ?? 'unknown',
        asrDevice: provider('asr')?.device ?? 'unknown',
        correction: provider('correction')?.name ?? 'unknown',
        correctionDevice: provider('correction')?.device ?? 'unknown'
      });
    }).catch(() => undefined);
    return () => client.dispose();
  }, []);

  const checkDevices = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await clientRef.current!.checkDevices();
      setGate(result);
    } catch (cause) {
      setGate({ ready: false, reason: 'unchecked' });
      setError(cause instanceof Error ? cause.message : '無法檢查耳機裝置');
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    setBusy(true);
    setError('');
    dispatch({ type: 'client.session_reset' });
    try {
      const response = await fetch('/api/v1/sessions', { method: 'POST' });
      if (!response.ok) throw new Error('無法建立 realtime session');
      const session = await response.json() as { id: string };
      setSessionId(session.id);
      await clientRef.current!.start(session.id);
      setActive(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '無法開始即時聆聽');
    } finally {
      setBusy(false);
    }
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

  return (
    <>
      <a className="skip-link" href="#studio-main">跳至主要內容</a>
      <Waves animated={!reducedMotion && active} />
      <div className="background-word background-word-top" aria-hidden="true">VOICE · SIGNAL · TEXT</div>
      <div className="background-word background-word-bottom" aria-hidden="true">LISTEN</div>
      <main id="studio-main" className="studio-shell">
        <nav className="studio-nav" aria-label="Realtime navigation">
          <a href="/"><ArrowLeft aria-hidden="true" /> Project Home</a>
          <span>ASR REALTIME · LOCAL</span>
        </nav>

        <header className="studio-header">
          <div>
            <p className="eyebrow">CONTINUOUS SPEECH EXPERIENCE</p>
            <h1 aria-label="Speak. See it flow.">Speak.<br /><span>See it flow.</span></h1>
            <p className="lede">聲音進來，文字成形。每次說話、停頓與校正，都由真實 pipeline event 即時呈現。</p>
          </div>
          <div className="session-chip" aria-label={`目前 session ${sessionId || '尚未建立'}`}>
            <span>SESSION</span><code>{sessionId || 'not started'}</code>
          </div>
        </header>

        {error && <div className="error-banner" role="alert"><strong>{error}</strong><span>請確認 worker 狀態與耳機連線後重試。</span></div>}
        {state.warning && <div className="warning-banner" role="status">Pipeline warning: {state.warning}</div>}

        <section className={`control-deck${gate.ready ? ' ready' : ''}`} aria-label="即時語音控制">
          <DeviceGate gate={gate} />
          <div className="actions">
            <button className="secondary-button" type="button" onClick={checkDevices} disabled={busy || active}>
              <ShieldCheck aria-hidden="true" /> {busy && !active ? '正在檢查…' : 'Check devices'}
            </button>
            {!active ? (
              <button className="primary-button" type="button" onClick={start} disabled={!gate.ready || busy} aria-label="開始即時聆聽">
                <Headphones aria-hidden="true" /> Start Listening
              </button>
            ) : (
              <button className="stop-button" type="button" onClick={stop} disabled={busy} aria-label="停止即時聆聽">
                <CircleStop aria-hidden="true" /> Stop Listening
              </button>
            )}
          </div>
        </section>

        <ProcessCycle stage={state.stage} reducedMotion={reducedMotion} />

        <div className="live-grid">
          <AudioStage samples={envelope} state={state.stream} />
          <section className="worker-card" aria-label="Inference worker devices">
            <div><p className="eyebrow">ACTIVE MODELS</p><span className={`worker-state${active ? ' live' : ''}`}>{active ? 'STREAMING' : 'STANDBY'}</span></div>
            <dl>
              <div><dt>VAD</dt><dd>{inference.vad}</dd></div>
              <div><dt>ASR</dt><dd>{inference.asr}<small>{inference.asrDevice}</small></dd></div>
              <div><dt>Correction</dt><dd>{inference.correction}<small>{inference.correctionDevice}</small></dd></div>
              <div><dt>Endpoint</dt><dd>{state.endpointMs || 900} ms<small>hard 1800 ms</small></dd></div>
              <div><dt>ASR Queue</dt><dd>{state.asrQueue} pending</dd></div>
            </dl>
          </section>
        </div>

        <TranscriptPanel rows={state.rows} />
        <UtteranceGraph rows={state.rows} completedUtteranceIds={state.completedUtteranceIds} />
        <p className="sr-status" aria-live="polite">{gate.ready ? 'Zone Vibe 100 輸入與輸出已確認' : '尚未檢查 Zone Vibe 100 輸入與輸出'}；{state.stage}</p>
      </main>
    </>
  );
}
