import {
  ArrowLeft,
  CheckCircle2,
  CircleDot,
  LockKeyhole,
  RefreshCw,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { checkAudioDevices, watchDeviceChanges } from '../audio/deviceGate';
import type { DeviceGateResult } from '../types';
import {
  getCloneStatus,
  synthesizeSpeech,
  validateReference,
} from './api';
import {
  createEphemeralAudioStore,
  createPlaybackAnalyser,
  createReferenceRecorder,
  type EphemeralAudioStore,
  type PlaybackAnalyser,
  type ReferenceRecorder,
} from './audio';
import { DeviceRuntimeGate } from './components/DeviceRuntimeGate';
import { TTSPlayPanel } from './components/TTSPlayPanel';
import { VoiceClonePanel } from './components/VoiceClonePanel';
import { VoiceOrb } from './components/VoiceOrb';
import {
  CATALOGS,
  LocaleContext,
  resolveLocale,
  type Locale,
} from './i18n';
import type {
  CloneStatus,
  CloneStudioState,
  ReferenceAssessment,
  StyleCue,
  SynthesisRequest,
} from './types';

type DeviceState = 'unchecked' | 'checking' | 'ready' | 'missing';

export type CloneStudioDependencies = {
  getStatus(): Promise<CloneStatus>;
  checkDevices(): Promise<DeviceGateResult>;
  validate(reference: Blob): Promise<ReferenceAssessment>;
  synthesize(request: SynthesisRequest): Promise<Blob>;
  recorder: ReferenceRecorder;
  audioStore: EphemeralAudioStore;
  playback: PlaybackAnalyser;
  watchDevices(invalidate: () => void): () => void;
};

function defaultDependencies(): CloneStudioDependencies {
  const mediaDevices = navigator.mediaDevices;
  return {
    getStatus: () => getCloneStatus(),
    checkDevices: () => checkAudioDevices(mediaDevices),
    validate: reference => validateReference(reference),
    synthesize: request => synthesizeSpeech(request),
    recorder: createReferenceRecorder(),
    audioStore: createEphemeralAudioStore(),
    playback: createPlaybackAnalyser(),
    watchDevices: invalidate => watchDeviceChanges(mediaDevices, invalidate),
  };
}

const ORB_LABELS: Record<CloneStudioState, keyof typeof CATALOGS.en> = {
  unavailable: 'orbUnavailable',
  idle: 'orbIdle',
  recording: 'orbRecording',
  validating: 'orbValidating',
  queued: 'orbQueued',
  generating: 'orbGenerating',
  'audio-ready': 'orbAudioReady',
  playing: 'orbPlaying',
  complete: 'orbComplete',
  error: 'orbError',
};

const QUALITY_LABELS: Record<ReferenceAssessment['quality'], keyof typeof CATALOGS.en> = {
  good: 'qualityGood',
  too_short: 'qualityTooShort',
  too_long: 'qualityTooLong',
  too_quiet: 'qualityTooQuiet',
  too_little_voice: 'qualityTooLittleVoice',
};

export function App({ dependencies }: { dependencies?: CloneStudioDependencies }) {
  const deps = useMemo(() => dependencies ?? defaultDependencies(), [dependencies]);
  const [locale, setLocale] = useState<Locale>(() => resolveLocale(
    window.location.search,
    localStorage.getItem('agent-speak-locale'),
  ));
  const t = CATALOGS[locale];
  const [activeTab, setActiveTab] = useState<'clone' | 'play'>('clone');
  const [status, setStatus] = useState<CloneStatus>();
  const [microphone, setMicrophone] = useState<DeviceState>('unchecked');
  const [speaker, setSpeaker] = useState<DeviceState>('unchecked');
  const [inputId, setInputId] = useState('');
  const [studioState, setStudioState] = useState<CloneStudioState>('unavailable');
  const [amplitude, setAmplitude] = useState(0);
  const [voiced, setVoiced] = useState(false);
  const [assessment, setAssessment] = useState<ReferenceAssessment>();
  const [hasReference, setHasReference] = useState(false);
  const [text, setText] = useState('');
  const [styleCues, setStyleCues] = useState<StyleCue[]>([]);
  const [useClone, setUseClone] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [recording, setRecording] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const [activity, setActivity] = useState(t.activityIdle);
  const [reducedMotion, setReducedMotion] = useState(false);
  const recordingStarted = useRef(0);

  const runtimeReady = Boolean(status?.ready);
  const devicesReady = microphone === 'ready' && speaker === 'ready';
  const controlsReady = runtimeReady && devicesReady;

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(Boolean(media?.matches));
    update();
    media?.addEventListener?.('change', update);
    return () => media?.removeEventListener?.('change', update);
  }, []);

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const next = await deps.getStatus();
        if (!alive) return;
        setStatus(next);
        setStudioState(current => {
          if (['recording', 'validating', 'queued', 'generating', 'audio-ready', 'playing'].includes(current)) {
            return current;
          }
          return next.ready ? 'idle' : 'unavailable';
        });
      } catch {
        if (!alive) return;
        setStatus({
          gpuMode: 'asr',
          accelerator: 'cpu',
          state: 'failed',
          model: 'voxcpm2',
          device: 'unknown',
          ready: false,
          errorCode: 'provider_unavailable',
          operatorHint: './run.sh --logs tts-worker',
        });
        setStudioState('unavailable');
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 3_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [deps]);

  useEffect(() => deps.recorder.subscribeAmplitude((next, hasVoice) => {
    setAmplitude(next);
    setVoiced(hasVoice);
  }), [deps]);

  useEffect(() => deps.playback.subscribeAmplitude(next => {
    setAmplitude(next);
    setVoiced(next >= 0.03);
  }), [deps]);

  useEffect(() => deps.playback.subscribeEnded(() => {
    setPlaying(false);
    setAmplitude(0);
    setVoiced(false);
    setStudioState('complete');
    setActivity(t.activityAudioReady);
  }), [deps, t.activityAudioReady]);

  useEffect(() => deps.watchDevices(() => {
    setMicrophone('unchecked');
    setSpeaker('unchecked');
    setInputId('');
    setRecording(false);
    setStudioState(status?.ready ? 'idle' : 'unavailable');
    setError(t.deviceError);
    void deps.recorder.discard();
  }), [deps, status?.ready, t.deviceError]);

  useEffect(() => {
    if (!recording) return;
    const update = () => setElapsed((performance.now() - recordingStarted.current) / 1_000);
    update();
    const timer = window.setInterval(update, 100);
    return () => window.clearInterval(timer);
  }, [recording]);

  useEffect(() => () => {
    void deps.recorder.discard();
    deps.playback.dispose();
    deps.audioStore.dispose();
  }, [deps]);

  useEffect(() => {
    setActivity(current => current === CATALOGS.en.activityIdle ? t.activityIdle : current);
    document.documentElement.lang = locale;
  }, [locale, t.activityIdle]);

  const chooseLocale = (next: Locale) => {
    setLocale(next);
    localStorage.setItem('agent-speak-locale', next);
    const url = new URL(window.location.href);
    url.searchParams.set('lang', next);
    window.history.replaceState({}, '', url);
  };

  const checkDevices = async () => {
    setMicrophone('checking');
    setSpeaker('checking');
    setError('');
    const gate = await deps.checkDevices();
    setMicrophone(gate.input ? 'ready' : 'missing');
    setSpeaker(gate.output ? 'ready' : 'missing');
    setInputId(gate.input?.deviceId ?? '');
    setActivity(gate.ready ? t.activityDevices : t.deviceError);
    if (!gate.ready) setError(t.deviceError);
  };

  const startRecording = async () => {
    if (!controlsReady) return;
    setError('');
    setElapsed(0);
    setAmplitude(0);
    await deps.recorder.start(inputId);
    recordingStarted.current = performance.now();
    setRecording(true);
    setStudioState('recording');
    setActivity(t.activityRecording);
  };

  const stopRecording = async () => {
    setRecording(false);
    setStudioState('validating');
    setActivity(t.activityValidating);
    try {
      const blob = await deps.recorder.stop();
      const result = await deps.validate(blob);
      setAssessment(result);
      if (result.quality === 'good') {
        deps.audioStore.setReference(blob);
        setHasReference(true);
        setActivity(t.activityReferenceReady);
        setStudioState('idle');
      } else {
        setError(t[QUALITY_LABELS[result.quality]]);
        setStudioState('error');
      }
    } catch {
      setError(t.generationError);
      setStudioState('error');
    }
    setAmplitude(0);
    setVoiced(false);
  };

  useEffect(() => {
    if (recording && elapsed >= 30) void stopRecording();
  }, [elapsed, recording]);

  const discardReference = () => {
    deps.audioStore.clearReference();
    setHasReference(false);
    setUseClone(false);
    setAssessment(undefined);
    setStudioState(runtimeReady ? 'idle' : 'unavailable');
  };

  const generate = async () => {
    if (!controlsReady || !text.trim()) return;
    setError('');
    setGenerated(false);
    deps.audioStore.clearGenerated();
    setStudioState('queued');
    setActivity(t.activityGenerating);
    await Promise.resolve();
    setStudioState('generating');
    try {
      const audio = await deps.synthesize({
        text: text.trim(),
        styleCues,
        useClone,
        reference: useClone ? deps.audioStore.reference : undefined,
      });
      deps.audioStore.setGenerated(audio);
      deps.playback.setSource(deps.audioStore.generatedUrl ?? '');
      setGenerated(true);
      setStudioState('audio-ready');
      setActivity(t.activityAudioReady);
    } catch {
      setError(t.generationError);
      setStudioState('error');
    }
  };

  const play = async () => {
    if (!generated) return;
    try {
      await deps.playback.play();
      setPlaying(true);
      setStudioState('playing');
      setActivity(t.activityPlaying);
    } catch {
      setError(t.playbackError);
      setStudioState('error');
    }
  };

  const stopPlayback = () => {
    deps.playback.stop();
    setPlaying(false);
    setAmplitude(0);
    setStudioState('complete');
    setActivity(t.activityAudioReady);
  };

  const orbLabel = t[ORB_LABELS[studioState]];
  const cueNames: Record<StyleCue, string> = {
    light_laugh: t.cueLightLaugh,
    snicker: t.cueSnicker,
    sigh: t.cueSigh,
    cough: t.cueCough,
    warm: t.cueWarm,
    cheerful: t.cueCheerful,
    soft: t.cueSoft,
    faster: t.cueFaster,
  };

  return (
    <LocaleContext.Provider value={{ locale, catalog: t }}>
      <div className="clone-studio">
        <div className="aurora aurora--one" aria-hidden="true" />
        <div className="aurora aurora--two" aria-hidden="true" />
        <header className="studio-nav">
          <a href={`/?lang=${locale}`} className="nav-home">
            <ArrowLeft size={16} />{t.back}
          </a>
          <a href={`/?lang=${locale}`} className="nav-brand"><i />{t.brand}</a>
          <label className="language-select">
            <span>{t.language}</span>
            <select value={locale} onChange={event => chooseLocale(event.target.value as Locale)}>
              <option value="en">EN</option>
              <option value="zh-TW">繁中</option>
              <option value="ja">日本語</option>
              <option value="ko">한국어</option>
            </select>
          </label>
        </header>

        <main>
          <section className="studio-hero">
            <div>
              <p className="eyebrow"><CircleDot size={13} />{t.eyebrow}</p>
              <h1>{t.title}</h1>
              <p>{t.subtitle}</p>
            </div>
            <button
              className="button button--device"
              disabled={microphone === 'checking'}
              onClick={checkDevices}
            >
              {microphone === 'checking' ? <RefreshCw className="spin" size={17} /> : <CheckCircle2 size={17} />}
              {microphone === 'checking' ? t.checkingDevices : t.checkDevices}
            </button>
          </section>

          <DeviceRuntimeGate
            microphone={microphone}
            speaker={speaker}
            status={status}
            hasReference={hasReference}
            labels={{
              microphone: t.microphone, speaker: t.speaker, cuda: t.cuda,
              worker: t.worker, model: t.model, reference: t.reference,
              ready: t.ready, waiting: t.waiting, missing: t.missing,
            }}
          />
          <p className="device-consent"><LockKeyhole size={14} />{t.deviceHint}</p>

          <section className="cockpit">
            <div className="mode-column">
              <div className="tabs" role="tablist" aria-label="TTS test mode">
                <button
                  aria-controls="clone-panel"
                  aria-selected={activeTab === 'clone'}
                  id="clone-tab"
                  onClick={() => setActiveTab('clone')}
                  onKeyDown={event => event.key === 'ArrowRight' && setActiveTab('play')}
                  role="tab"
                >{t.cloneTab}</button>
                <button
                  aria-controls="play-panel"
                  aria-selected={activeTab === 'play'}
                  id="play-tab"
                  onClick={() => setActiveTab('play')}
                  onKeyDown={event => event.key === 'ArrowLeft' && setActiveTab('clone')}
                  role="tab"
                >{t.playTab}</button>
              </div>
              <div
                aria-labelledby="clone-tab"
                hidden={activeTab !== 'clone'}
                id="clone-panel"
                role="tabpanel"
              >
                <VoiceClonePanel
                  title={t.cloneTitle}
                  description={t.cloneDescription}
                  zeroShot={t.zeroShot}
                  recording={recording}
                  enabled={controlsReady}
                  hasReference={hasReference}
                  assessment={assessment}
                  amplitude={amplitude}
                  labels={{
                    start: t.startRecording, stop: t.stopRecording, replace: t.replaceRecording,
                    discard: t.discardReference, duration: t.duration, inputLevel: t.inputLevel,
                    voiceRatio: t.voiceRatio, quality: t.quality,
                    qualityText: assessment ? t[QUALITY_LABELS[assessment.quality]] : t.waiting,
                  }}
                  onStart={() => void startRecording()}
                  onStop={() => void stopRecording()}
                  onDiscard={discardReference}
                />
              </div>
              <div
                aria-labelledby="play-tab"
                hidden={activeTab !== 'play'}
                id="play-panel"
                role="tabpanel"
              >
                <TTSPlayPanel
                  title={t.ttsTitle}
                  description={t.ttsDescription}
                  text={text}
                  selectedCues={styleCues}
                  useClone={useClone}
                  hasReference={hasReference}
                  canGenerate={controlsReady}
                  generated={generated}
                  generating={studioState === 'queued' || studioState === 'generating'}
                  playing={playing}
                  labels={{
                    text: t.textLabel, placeholder: t.textPlaceholder, cues: t.styleCues,
                    cueHint: t.cueHint, cueNames, useClone: t.useClone,
                    defaultVoice: t.defaultVoice, generate: t.generate, generating: t.generating,
                    play: t.play, stop: t.stopPlayback, generatedHint: t.generatedHint,
                  }}
                  onText={setText}
                  onToggleCue={cue => setStyleCues(current =>
                    current.includes(cue) ? current.filter(value => value !== cue) : [...current, cue])}
                  onUseClone={setUseClone}
                  onGenerate={() => void generate()}
                  onPlay={() => void play()}
                  onStop={stopPlayback}
                />
              </div>
            </div>

            <aside className="orb-column">
              <VoiceOrb
                state={studioState}
                amplitude={amplitude}
                voiced={voiced}
                reducedMotion={reducedMotion}
                label={orbLabel}
              />
              {recording && <strong className="recording-time">{elapsed.toFixed(1)} / 30.0 s</strong>}
              <div className="activity-card">
                <span>{t.activityTitle}</span>
                <p aria-live="polite">{activity}</p>
                {error && <p className="activity-error" role="alert">{error}</p>}
              </div>
            </aside>
          </section>
          <footer className="privacy-note"><LockKeyhole size={15} />{t.privacy}</footer>
        </main>
      </div>
    </LocaleContext.Provider>
  );
}
