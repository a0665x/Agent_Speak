import { useEffect, useRef } from 'react';
import { useI18n, type MessageKey } from '../i18n';

export function AudioStage({ samples, state }: { samples: number[]; state: string }) {
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context.scale(ratio, ratio);
    context.clearRect(0, 0, width, height);
    context.strokeStyle = '#bdd4ff';
    context.lineWidth = 2;
    context.beginPath();
    const values = samples.length ? samples : Array.from({ length: 32 }, () => 0.03);
    values.forEach((value, index) => {
      const x = index * width / Math.max(1, values.length - 1);
      const y = height / 2 - Math.min(1, value) * height * 0.42;
      if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
    });
    for (let index = values.length - 1; index >= 0; index -= 1) {
      const x = index * width / Math.max(1, values.length - 1);
      const y = height / 2 + Math.min(1, values[index]) * height * 0.42;
      context.lineTo(x, y);
    }
    context.closePath();
    context.stroke();
  }, [samples]);

  return (
    <figure className="audio-stage">
      <canvas ref={canvasRef} aria-label={t('audio.waveform', { value: stateLabel(state, t) })} />
      <figcaption><span className={`state-dot state-${state}`} /> {stateLabel(state, t)}</figcaption>
    </figure>
  );
}

function stateLabel(state: string, t: (key: MessageKey) => string): string {
  const keys: Record<string, MessageKey> = {
    ready: 'audio.ready', listening: 'audio.listening', speech: 'audio.speech', endpoint: 'audio.endpoint',
    finalizing: 'audio.finalizing', correcting: 'audio.correcting', stopped: 'audio.stopped'
  };
  return keys[state] ? t(keys[state]) : state;
}
