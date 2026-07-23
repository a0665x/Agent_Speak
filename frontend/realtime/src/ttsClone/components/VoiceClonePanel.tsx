import { Check, Mic, RotateCcw, Square, Trash2 } from 'lucide-react';
import type { ReferenceAssessment } from '../types';

export function VoiceClonePanel({
  title,
  description,
  zeroShot,
  recording,
  enabled,
  hasReference,
  assessment,
  amplitude,
  labels,
  onStart,
  onStop,
  onDiscard,
}: {
  title: string;
  description: string;
  zeroShot: string;
  recording: boolean;
  enabled: boolean;
  hasReference: boolean;
  assessment?: ReferenceAssessment;
  amplitude: number;
  labels: {
    start: string;
    stop: string;
    replace: string;
    discard: string;
    duration: string;
    inputLevel: string;
    voiceRatio: string;
    quality: string;
    qualityText: string;
  };
  onStart(): void;
  onStop(): void;
  onDiscard(): void;
}) {
  return (
    <div className="mode-panel__content">
      <div className="panel-heading">
        <span className="panel-heading__icon"><Mic aria-hidden="true" /></span>
        <div><h2>{title}</h2><p>{description}</p></div>
      </div>
      <div className="level-strip" aria-label={labels.inputLevel}>
        {Array.from({ length: 24 }, (_, index) => (
          <i
            aria-hidden="true"
            key={index}
            style={{ '--level': Math.max(0.08, amplitude * (0.55 + (index % 5) * 0.11)) } as React.CSSProperties}
          />
        ))}
      </div>
      {assessment && (
        <dl className="reference-metrics">
          <div><dt>{labels.duration}</dt><dd>{assessment.durationSeconds.toFixed(1)} s</dd></div>
          <div><dt>{labels.inputLevel}</dt><dd>{Math.round(assessment.rms * 100)}%</dd></div>
          <div><dt>{labels.voiceRatio}</dt><dd>{Math.round(assessment.voicedRatio * 100)}%</dd></div>
          <div><dt>{labels.quality}</dt><dd><Check size={14} />{labels.qualityText}</dd></div>
        </dl>
      )}
      <div className="panel-actions">
        {recording ? (
          <button className="button button--primary" onClick={onStop}>
            <Square size={16} fill="currentColor" />{labels.stop}
          </button>
        ) : (
          <button className="button button--primary" disabled={!enabled} onClick={onStart}>
            {hasReference ? <RotateCcw size={17} /> : <Mic size={17} />}
            {hasReference ? labels.replace : labels.start}
          </button>
        )}
        {hasReference && !recording && (
          <button className="button button--quiet" onClick={onDiscard}>
            <Trash2 size={16} />{labels.discard}
          </button>
        )}
      </div>
      <p className="zero-shot-note"><span aria-hidden="true">01</span>{zeroShot}</p>
    </div>
  );
}
