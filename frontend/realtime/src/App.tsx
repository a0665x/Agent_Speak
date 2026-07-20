import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { Activity, CircleStop, Headphones, ShieldCheck } from 'lucide-react';
import { RealtimeClient } from './audio/realtimeClient';
import { AudioStage } from './components/AudioStage';
import { DeviceGate } from './components/DeviceGate';
import { PipelineRail } from './components/PipelineRail';
import { TranscriptPanel } from './components/TranscriptPanel';
import { initialState, realtimeReducer } from './state/reducer';
import type { DeviceGateResult, RealtimeEvent } from './types';
import { Waves } from './vendor/reactbits/Waves';

export type AppProps = { forceReducedMotion?: boolean };

export function App({ forceReducedMotion = false }: AppProps) {
  const [state, dispatch] = useReducer(realtimeReducer, initialState);
  const [gate, setGate] = useState<DeviceGateResult>({ ready: false, reason: 'unchecked' });
  const [envelope, setEnvelope] = useState<number[]>([]);
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [devices, setDevices] = useState({ asr: 'unknown', correction: 'unknown' });
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
      const providers = payload.providers as Array<{ stage: string; device: string }>;
      setDevices({
        asr: providers.find(item => item.stage === 'asr')?.device ?? 'unknown',
        correction: providers.find(item => item.stage === 'correction')?.device ?? 'unknown'
      });
    }).catch(() => undefined);
    return () => client.dispose();
  }, []);

  const checkDevices = async () => {
    setBusy(true);
    setError('');
    const result = await clientRef.current!.checkDevices();
    setGate(result);
    setBusy(false);
  };

  const start = async () => {
    setBusy(true);
    setError('');
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
    await clientRef.current?.stop('user');
    setActive(false);
    setBusy(false);
  };

  return (
    <>
      <a className="skip-link" href="#studio-main">跳至主要內容</a>
      <Waves animated={!reducedMotion && active} />
      <main id="studio-main" className="studio-shell">
        <header className="studio-header">
          <div>
            <p className="eyebrow"><Activity size={16} /> AGENT SPEAK / REALTIME</p>
            <h1>Speech<br />Studio</h1>
            <p className="lede">持續 VAD、adaptive endpoint、rolling ASR 與逐句中文校正。只做轉錄，不呼叫 Agent 或 TTS。</p>
          </div>
          <div className="session-chip" aria-label={`目前 session ${sessionId || '尚未建立'}`}>
            <span>SESSION</span><code>{sessionId || 'not started'}</code>
          </div>
        </header>

        {error && <div className="error-banner" role="alert">{error}<span>請確認 worker 狀態與耳機連線後重試。</span></div>}
        {state.warning && <div className="warning-banner" role="status">Pipeline warning: {state.warning}</div>}

        <section className="control-deck" aria-label="即時語音控制">
          <DeviceGate gate={gate} />
          <div className="actions">
            <button className="secondary-button" type="button" onClick={checkDevices} disabled={busy || active}>
              <ShieldCheck /> {busy && !active ? '正在檢查…' : '檢查耳機裝置'}
            </button>
            {!active ? (
              <button className="primary-button" type="button" onClick={start} disabled={!gate.ready || busy} aria-label="開始即時聆聽">
                <Headphones /> 開始即時聆聽
              </button>
            ) : (
              <button className="stop-button" type="button" onClick={stop} disabled={busy} aria-label="停止即時聆聽">
                <CircleStop /> 停止即時聆聽
              </button>
            )}
          </div>
        </section>

        <div className="studio-grid">
          <div className="main-column">
            <AudioStage samples={envelope} state={state.stream} />
            <TranscriptPanel rows={state.rows} />
          </div>
          <div className="side-column">
            <PipelineRail state={state.stream} queue={state.asrQueue} endpointMs={state.endpointMs} />
            <section className="worker-card" aria-label="Inference worker devices">
              <p className="eyebrow">INFERENCE</p>
              <dl><div><dt>ASR</dt><dd>{devices.asr}</dd></div><div><dt>Correction</dt><dd>{devices.correction}</dd></div></dl>
            </section>
          </div>
        </div>
        <p className="sr-status" aria-live="polite">{gate.ready ? 'Zone Vibe 100 輸入與輸出已確認' : '尚未檢查 Zone Vibe 100 輸入與輸出'}；{state.stream}</p>
      </main>
    </>
  );
}
