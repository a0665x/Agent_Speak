import { useEffect, useRef } from 'react';
import { useI18n, type MessageKey } from '../i18n';
import { buildSignalRibbons, type SignalPoint } from '../audio/signalRibbons';

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
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    const gradient = context.createLinearGradient(0, 0, width, 0);
    gradient.addColorStop(0, '#8fcfff');
    gradient.addColorStop(0.48, '#d7c4ff');
    gradient.addColorStop(1, '#ffb9dc');
    const ribbons = buildSignalRibbons(samples, width, height);
    [...ribbons].reverse().forEach((ribbon, reverseIndex) => {
      context.save();
      context.globalAlpha = ribbon.opacity;
      context.fillStyle = gradient;
      context.shadowColor = reverseIndex === ribbons.length - 1 ? 'rgba(176, 207, 255, .72)' : 'rgba(190, 168, 255, .34)';
      context.shadowBlur = reverseIndex === ribbons.length - 1 ? 22 : 12;
      traceRibbon(context, ribbon.upper, ribbon.lower);
      context.fill();
      context.restore();
    });
    context.save();
    context.globalAlpha = 0.55;
    context.strokeStyle = '#f4f7ff';
    context.lineWidth = 0.8;
    traceCurve(context, ribbons[0].upper);
    context.stroke();
    context.restore();
  }, [samples]);

  return (
    <figure className="audio-stage">
      <canvas ref={canvasRef} aria-label={t('audio.waveform', { value: stateLabel(state, t) })} />
      <figcaption><span className={`state-dot state-${state}`} /> {stateLabel(state, t)}</figcaption>
    </figure>
  );
}

function traceRibbon(context: CanvasRenderingContext2D, upper: SignalPoint[], lower: SignalPoint[]) {
  traceCurve(context, upper);
  traceCurve(context, [...lower].reverse(), false);
  context.closePath();
}

function traceCurve(context: CanvasRenderingContext2D, points: SignalPoint[], begin = true) {
  if (!points.length) return;
  if (begin) context.beginPath();
  context.moveTo(points[0].x, points[0].y);
  for (let index = 1; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    context.quadraticCurveTo(current.x, current.y, (current.x + next.x) / 2, (current.y + next.y) / 2);
  }
  const last = points[points.length - 1];
  context.lineTo(last.x, last.y);
}

function stateLabel(state: string, t: (key: MessageKey) => string): string {
  const keys: Record<string, MessageKey> = {
    ready: 'audio.ready', listening: 'audio.listening', speech: 'audio.speech', endpoint: 'audio.endpoint',
    finalizing: 'audio.finalizing', correcting: 'audio.correcting', stopped: 'audio.stopped'
  };
  return keys[state] ? t(keys[state]) : state;
}
