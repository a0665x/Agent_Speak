import { useEffect, useRef } from 'react';
import type { CloneStudioState } from '../types';

export function VoiceOrb({
  state,
  amplitude,
  voiced,
  reducedMotion,
  label,
}: {
  state: CloneStudioState;
  amplitude: number;
  voiced: boolean;
  reducedMotion: boolean;
  label: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    let frame = 0;
    let animation = 0;
    const draw = () => {
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      const size = canvas.clientWidth || 320;
      if (canvas.width !== size * ratio) {
        canvas.width = size * ratio;
        canvas.height = size * ratio;
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, size, size);
      const center = size / 2;
      const energy = reducedMotion ? 0.08 : Math.max(0.04, Math.min(1, amplitude));
      const active = ['recording', 'generating', 'playing', 'validating', 'queued'].includes(state);
      const pulse = active && !reducedMotion ? Math.sin(frame / 18) * 5 : 0;
      for (let ring = 3; ring >= 0; ring -= 1) {
        context.beginPath();
        context.arc(center, center, size * (0.27 + ring * 0.045) + energy * 18 + pulse, 0, Math.PI * 2);
        context.strokeStyle = `rgba(139, 184, 255, ${0.06 + (3 - ring) * 0.035})`;
        context.lineWidth = 1;
        context.stroke();
      }
      frame += 1;
      if (!reducedMotion) animation = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animation);
  }, [amplitude, reducedMotion, state]);

  const scale = reducedMotion ? 1 : 1 + Math.min(0.09, amplitude * 0.09);
  return (
    <div
      className="voice-orb"
      data-state={state}
      data-voiced={String(voiced)}
      data-reduced-motion={String(reducedMotion)}
      data-testid="voice-orb"
      style={{ '--orb-scale': scale } as React.CSSProperties}
    >
      <canvas ref={canvasRef} aria-hidden="true" />
      <div className="voice-orb__halo" aria-hidden="true" />
      <div className="voice-orb__core" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="voice-orb__label" role="status" aria-live="polite">
        <i aria-hidden="true" />
        {label}
      </div>
    </div>
  );
}
