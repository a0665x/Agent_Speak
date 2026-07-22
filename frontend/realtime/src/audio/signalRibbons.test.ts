import { describe, expect, test } from 'vitest';
import { buildSignalRibbons, smoothEnvelope } from './signalRibbons';

describe('signal ribbon geometry', () => {
  test('smooths sharp samples without changing the sample count', () => {
    expect(smoothEnvelope([0, 1, 0])).toEqual([0.25, 0.5, 0.25]);
  });

  test('builds centered symmetric layers with distinct amplitudes', () => {
    const ribbons = buildSignalRibbons([0, 1, 0], 120, 80);
    expect(ribbons).toHaveLength(3);
    expect(ribbons[0].upper[1].y + ribbons[0].lower[1].y).toBeCloseTo(80);
    expect(ribbons[0].lower[1].y - ribbons[0].upper[1].y)
      .toBeGreaterThan(ribbons[2].lower[1].y - ribbons[2].upper[1].y);
    expect(ribbons[0].upper[0].x).toBe(0);
    expect(ribbons[0].upper[2].x).toBe(120);
  });
});
