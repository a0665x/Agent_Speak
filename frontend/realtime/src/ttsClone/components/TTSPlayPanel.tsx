import { AudioLines, Pause, Play, Sparkles } from 'lucide-react';
import type { StyleCue } from '../types';

const CUES: StyleCue[] = [
  'light_laugh', 'snicker', 'sigh', 'cough', 'warm', 'cheerful', 'soft', 'faster',
];

export function TTSPlayPanel({
  title,
  description,
  text,
  selectedCues,
  useClone,
  hasReference,
  canGenerate,
  generated,
  generating,
  playing,
  labels,
  onText,
  onToggleCue,
  onUseClone,
  onGenerate,
  onPlay,
  onStop,
}: {
  title: string;
  description: string;
  text: string;
  selectedCues: StyleCue[];
  useClone: boolean;
  hasReference: boolean;
  canGenerate: boolean;
  generated: boolean;
  generating: boolean;
  playing: boolean;
  labels: {
    text: string;
    placeholder: string;
    cues: string;
    cueHint: string;
    cueNames: Record<StyleCue, string>;
    useClone: string;
    defaultVoice: string;
    generate: string;
    generating: string;
    play: string;
    stop: string;
    generatedHint: string;
  };
  onText(value: string): void;
  onToggleCue(cue: StyleCue): void;
  onUseClone(value: boolean): void;
  onGenerate(): void;
  onPlay(): void;
  onStop(): void;
}) {
  return (
    <div className="mode-panel__content">
      <div className="panel-heading">
        <span className="panel-heading__icon"><AudioLines aria-hidden="true" /></span>
        <div><h2>{title}</h2><p>{description}</p></div>
      </div>
      <label className="text-field">
        <span>{labels.text}</span>
        <textarea
          aria-label={labels.text}
          maxLength={20_000}
          placeholder={labels.placeholder}
          rows={5}
          value={text}
          onChange={event => onText(event.target.value)}
        />
        <small>{text.length.toLocaleString()} / 20,000</small>
      </label>
      <fieldset className="cue-field">
        <legend>{labels.cues}</legend>
        <div className="cue-grid">
          {CUES.map(cue => (
            <button
              aria-pressed={selectedCues.includes(cue)}
              className="cue"
              key={cue}
              onClick={() => onToggleCue(cue)}
              type="button"
            >
              {labels.cueNames[cue]}
            </button>
          ))}
        </div>
        <small>{labels.cueHint}</small>
      </fieldset>
      <label className={`clone-toggle ${!hasReference ? 'clone-toggle--disabled' : ''}`}>
        <input
          checked={useClone}
          disabled={!hasReference}
          onChange={event => onUseClone(event.target.checked)}
          type="checkbox"
        />
        <span><strong>{labels.useClone}</strong><small>{labels.defaultVoice}</small></span>
      </label>
      <div className="panel-actions">
        <button
          className="button button--primary"
          disabled={!canGenerate || !text.trim() || generating}
          onClick={onGenerate}
        >
          <Sparkles size={17} />{generating ? labels.generating : labels.generate}
        </button>
        {playing ? (
          <button className="button button--play" onClick={onStop}>
            <Pause fill="currentColor" size={16} />{labels.stop}
          </button>
        ) : (
          <button className="button button--play" disabled={!generated} onClick={onPlay}>
            <Play fill="currentColor" size={16} />{labels.play}
          </button>
        )}
      </div>
      <p className="generated-note">{labels.generatedHint}</p>
    </div>
  );
}
