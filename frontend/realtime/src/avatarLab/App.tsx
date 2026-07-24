import {
  Brain,
  CirclePause,
  Ear,
  MessageCircle,
  Pause,
  Play,
  RefreshCw,
  Smile,
  TriangleAlert,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { HenryAvatar } from '../../../../AI_Avatar/frontend/components/HenryAvatar';
import {
  ClipScheduler,
  type ClipSchedulerSnapshot,
} from '../../../../AI_Avatar/frontend/controllers/ClipScheduler';
import { PngSequenceRenderer } from '../../../../AI_Avatar/frontend/renderers/PngSequenceRenderer';
import type {
  AvatarState,
  LoadedAvatarAssets,
} from '../../../../AI_Avatar/frontend/types/avatar';
import { ParticleField } from '../components/ParticleField';
import { loadManifest } from './manifest';

const STATE_LABELS: Record<AvatarState, string> = {
  idle: 'Idle',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  happy: 'Happy',
  error: 'Error',
};

const STATE_ICONS = {
  idle: CirclePause,
  listening: Ear,
  thinking: Brain,
  speaking: MessageCircle,
  happy: Smile,
  error: TriangleAlert,
} satisfies Record<AvatarState, typeof CirclePause>;

const PERSISTENT_STATES: readonly AvatarState[] = [
  'idle',
  'listening',
  'thinking',
  'speaking',
];
const REACTION_STATES: readonly AvatarState[] = ['happy', 'error'];

export interface AvatarLabProps {
  manifestLoader?: () => Promise<LoadedAvatarAssets>;
}

function sameSnapshot(
  previous: ClipSchedulerSnapshot | null,
  next: ClipSchedulerSnapshot,
): boolean {
  return Boolean(
    previous
    && previous.playingState === next.playingState
    && previous.pendingState === next.pendingState
    && previous.frameId === next.frameId
    && previous.frameIndex === next.frameIndex
    && previous.paused === next.paused
  );
}

export function App({
  manifestLoader = loadManifest,
}: AvatarLabProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const schedulerRef = useRef<ClipScheduler | null>(null);
  const rendererRef = useRef<PngSequenceRenderer | null>(null);
  const [assets, setAssets] = useState<LoadedAvatarAssets | null>(null);
  const [snapshot, setSnapshot] = useState<ClipSchedulerSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    manifestLoader()
      .then((loaded) => {
        if (!cancelled) {
          setAssets(loaded);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : String(cause));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [manifestLoader]);

  useEffect(() => {
    if (!assets || !canvasRef.current) {
      return;
    }
    const scheduler = new ClipScheduler(assets.manifest, 'idle');
    const renderer = new PngSequenceRenderer(
      canvasRef.current,
      assets.manifest.viewport,
    );
    schedulerRef.current = scheduler;
    rendererRef.current = renderer;
    renderer.preload(assets.preload.images);
    const initial = scheduler.snapshot();
    renderer.draw(initial.frameId);
    setSnapshot(initial);
    const update = () => {
      const next = scheduler.snapshot();
      setSnapshot((previous) => (sameSnapshot(previous, next) ? previous : next));
    };
    const unsubscribeSelected = scheduler.events.on('state.selected', update);
    const unsubscribeCompleted = scheduler.events.on('loop.completed', update);
    const unsubscribeFailed = renderer.events.on(
      'renderer.failed',
      ({ error: renderError }) => setError(renderError.message),
    );
    renderer.start((timestamp) => {
      const frameId = scheduler.advance(timestamp);
      update();
      return frameId;
    });
    return () => {
      unsubscribeSelected();
      unsubscribeCompleted();
      unsubscribeFailed();
      renderer.dispose();
      schedulerRef.current = null;
      rendererRef.current = null;
    };
  }, [assets]);

  const ready = Boolean(assets?.preload.ready && snapshot && !error);
  const selectState = (state: AvatarState) => {
    const scheduler = schedulerRef.current;
    if (!scheduler || !scheduler.select(state)) {
      return;
    }
    setSnapshot(scheduler.snapshot());
  };
  const togglePause = () => {
    const scheduler = schedulerRef.current;
    const renderer = rendererRef.current;
    if (!scheduler || !renderer || !snapshot) {
      return;
    }
    if (snapshot.paused) {
      scheduler.resume();
      renderer.resume();
    } else {
      scheduler.pause();
      renderer.pause();
    }
    setSnapshot(scheduler.snapshot());
  };
  const restart = () => {
    const scheduler = schedulerRef.current;
    const renderer = rendererRef.current;
    if (!scheduler || !renderer) {
      return;
    }
    scheduler.restart();
    const next = scheduler.snapshot();
    renderer.restart(next.frameId);
    setSnapshot(next);
  };

  const renderStateButtons = (states: readonly AvatarState[]) => (
    <div className="state-grid">
      {states.map((state) => {
        const Icon = STATE_ICONS[state];
        const queued = snapshot?.pendingState === state;
        const playing = snapshot?.playingState === state;
        return (
          <button
            key={state}
            type="button"
            className="state-button"
            data-playing={String(playing)}
            data-queued={String(queued)}
            disabled={!ready}
            onClick={() => selectState(state)}
            aria-pressed={playing}
          >
            <Icon size={18} aria-hidden="true" />
            <span>{STATE_LABELS[state]}</span>
            <i aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );

  return (
    <main className="avatar-lab">
      <ParticleField profile="subtle" />
      <div className="ambient-orb ambient-orb--one" aria-hidden="true" />
      <div className="ambient-orb ambient-orb--two" aria-hidden="true" />

      <header className="lab-header">
        <a href="/" className="brand" aria-label="Agent Speak home">
          <span aria-hidden="true">A</span>
          Agent Speak
        </a>
        <div className="asset-status" data-ready={String(ready)} role="status">
          <i aria-hidden="true" />
          {error ? 'Assets Unavailable' : ready ? 'Assets Ready' : 'Preparing Assets'}
        </div>
      </header>

      <section className="lab-intro">
        <p className="eyebrow">AI AVATAR · MOTION LAB</p>
        <h1>One character. Every moment, in motion.</h1>
        <p>
          Preview Henry&apos;s shared-boundary loops and queue the next state
          without interrupting the current gesture.
        </p>
      </section>

      <section className="motion-workspace" aria-label="Avatar motion controls">
        <div className="stage-card">
          <div className="stage-grid" aria-hidden="true" />
          <HenryAvatar
            ref={canvasRef}
            width={assets?.manifest.viewport.width ?? 512}
            height={assets?.manifest.viewport.height ?? 512}
            status={error ? 'error' : ready ? 'ready' : 'loading'}
          />
          <div className="playback-status" aria-live="polite">
            <span>
              Playing: {snapshot ? STATE_LABELS[snapshot.playingState] : '—'}
            </span>
            <span>
              Queued: {snapshot?.pendingState
                ? STATE_LABELS[snapshot.pendingState]
                : 'None'}
            </span>
          </div>
        </div>

        <aside className="control-card">
          <div className="control-section">
            <div>
              <p className="section-kicker">Persistent states</p>
              <h2>Choose a core loop</h2>
            </div>
            {renderStateButtons(PERSISTENT_STATES)}
          </div>
          <div className="control-section control-section--compact">
            <div>
              <p className="section-kicker">Reactions</p>
              <h2>Trigger a response</h2>
            </div>
            {renderStateButtons(REACTION_STATES)}
          </div>
          <div className="transport">
            <button type="button" disabled={!ready} onClick={togglePause}>
              {snapshot?.paused
                ? <Play size={17} aria-hidden="true" />
                : <Pause size={17} aria-hidden="true" />}
              {snapshot?.paused ? 'Resume' : 'Pause'}
            </button>
            <button type="button" disabled={!ready} onClick={restart}>
              <RefreshCw size={17} aria-hidden="true" />
              Restart
            </button>
          </div>
          {error && <p className="lab-error" role="alert">{error}</p>}
        </aside>
      </section>

      <details className="runtime-details">
        <summary>Runtime details</summary>
        <dl>
          <div><dt>Clip</dt><dd>{snapshot?.clipId ?? '—'}</dd></div>
          <div><dt>Frame</dt><dd>{snapshot?.frameId ?? '—'}</dd></div>
          <div><dt>FPS</dt><dd>{snapshot && assets
            ? assets.manifest.clips[snapshot.clipId].fps
            : '—'}</dd></div>
          <div><dt>Anchor</dt><dd>{assets
            ? `${assets.manifest.viewport.anchor_x}, ${assets.manifest.viewport.anchor_y}`
            : '—'}</dd></div>
          <div><dt>Preloaded</dt><dd>{assets?.preload.loaded ?? 0} frames</dd></div>
          <div><dt>Quality</dt><dd>Approved · shared S0</dd></div>
        </dl>
      </details>
    </main>
  );
}
