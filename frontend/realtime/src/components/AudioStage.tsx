import { useEffect, useRef } from 'react';

export function AudioStage({ samples, state }: { samples: number[]; state: string }) {
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
    context.strokeStyle = '#5eead4';
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
      <canvas ref={canvasRef} aria-label={`即時麥克風波形，目前狀態 ${state}`} />
      <figcaption><span className={`state-dot state-${state}`} /> {stateLabel(state)}</figcaption>
    </figure>
  );
}

function stateLabel(state: string): string {
  return ({ ready: '等待裝置', listening: '正在聆聽', speech: '偵測到語音', endpoint: '判斷句尾', finalizing: '最終辨識', correcting: '校正文字', stopped: '已停止' } as Record<string, string>)[state] ?? state;
}
