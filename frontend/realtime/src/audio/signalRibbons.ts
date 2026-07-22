export type SignalPoint = { x: number; y: number };
export type SignalRibbon = { upper: SignalPoint[]; lower: SignalPoint[]; opacity: number };

export function smoothEnvelope(samples: number[]): number[] {
  return samples.map((value, index) => {
    const previous = samples[index - 1] ?? value;
    const next = samples[index + 1] ?? value;
    return clamp((previous + value * 2 + next) / 4);
  });
}

export function buildSignalRibbons(
  samples: number[],
  width: number,
  height: number,
): SignalRibbon[] {
  const values = smoothEnvelope(samples.length ? samples : Array.from({ length: 48 }, () => 0.025));
  const center = height / 2;
  const scales = [0.9, 0.62, 0.36];
  return scales.map((scale, layer) => {
    const points = values.map((value, index) => {
      const x = index * width / Math.max(1, values.length - 1);
      const organic = 0.82 + 0.18 * Math.sin(index * 0.73 + layer * 1.7);
      const amplitude = Math.max(1.2, clamp(value) * height * 0.42 * scale * organic);
      return { x, amplitude };
    });
    return {
      upper: points.map(({ x, amplitude }) => ({ x, y: center - amplitude })),
      lower: points.map(({ x, amplitude }) => ({ x, y: center + amplitude })),
      opacity: [0.78, 0.34, 0.17][layer],
    };
  });
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}
