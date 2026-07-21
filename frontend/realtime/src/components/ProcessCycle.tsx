import { useEffect, useRef, useState } from 'react';
import { AudioLines, Ear, MessageSquareText, Sparkles, TimerReset } from 'lucide-react';
import type { PipelineStage } from '../types';

const TRAIL_MS = 1450;

const stages = [
  { key: 'listening', label: 'Listening', detail: 'Awaiting voice', icon: Ear },
  { key: 'voice', label: 'Voice detected', detail: 'VAD active', icon: AudioLines },
  { key: 'asr', label: 'ASR partial', detail: 'Rolling text', icon: MessageSquareText },
  { key: 'endpoint', label: 'Endpoint', detail: 'Pause / resume', icon: TimerReset },
  { key: 'correction', label: 'Correction', detail: 'Final text', icon: Sparkles },
] as const;

type VisibleStage = typeof stages[number]['key'];

export function ProcessCycle({ stage, reducedMotion }: { stage: PipelineStage; reducedMotion: boolean }) {
  const previousRef = useRef(stage);
  const [trail, setTrail] = useState<VisibleStage | null>(null);

  useEffect(() => {
    const previous = previousRef.current;
    previousRef.current = stage;
    if (reducedMotion || previous === stage || !isVisibleStage(previous)) {
      setTrail(null);
      return;
    }
    setTrail(previous);
    const timer = window.setTimeout(() => setTrail(null), TRAIL_MS);
    return () => window.clearTimeout(timer);
  }, [stage, reducedMotion]);

  return (
    <section className="process-cycle" aria-labelledby="process-cycle-title">
      <div className="process-heading">
        <div><p className="eyebrow">CONTINUOUS CYCLE</p><h2 id="process-cycle-title">Realtime processing</h2></div>
        <span className="current-phase" role="status">{stageLabel(stage)}</span>
      </div>
      <ol className="process-track">
        {stages.map(({ key, label, detail, icon: Icon }, index) => {
          const state = stage === key ? 'active' : trail === key ? 'trail' : 'idle';
          return (
            <li className="process-stage" data-state={state} data-testid={`stage-${key}`} key={key}>
              <span className="stage-node"><Icon aria-hidden="true" /></span>
              <span className="stage-copy"><strong>{label}</strong><small>{detail}</small></span>
              <span className="stage-index" aria-hidden="true">0{index + 1}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function isVisibleStage(stage: PipelineStage): stage is VisibleStage {
  return stages.some(item => item.key === stage);
}

function stageLabel(stage: PipelineStage): string {
  return stages.find(item => item.key === stage)?.label.toUpperCase() ?? stage.toUpperCase();
}
