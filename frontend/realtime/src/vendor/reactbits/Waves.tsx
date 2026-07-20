import { useEffect, useRef } from 'react';
import './Waves.css';

export function Waves({ animated = true }: { animated?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!animated) return;
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    let frame = 0;
    let phase = 0;
    const draw = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const ratio = window.devicePixelRatio || 1;
      if (canvas.width !== width * ratio || canvas.height !== height * ratio) {
        canvas.width = width * ratio;
        canvas.height = height * ratio;
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
      }
      context.clearRect(0, 0, width, height);
      for (let line = 0; line < 8; line += 1) {
        context.beginPath();
        context.strokeStyle = `rgba(94, 234, 212, ${0.04 + line * 0.012})`;
        for (let x = 0; x <= width; x += 12) {
          const y = height * (line + 1) / 9 + Math.sin(x * 0.012 + phase + line * 0.7) * 18;
          if (x === 0) context.moveTo(x, y); else context.lineTo(x, y);
        }
        context.stroke();
      }
      phase += 0.012;
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [animated]);
  return <div className="ambient-waves" data-testid="ambient-waves" data-animated={animated}><canvas ref={canvasRef} /></div>;
}
