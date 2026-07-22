import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(cleanup);

HTMLCanvasElement.prototype.getContext = (() => ({
  beginPath() {}, clearRect() {}, closePath() {}, fill() {}, lineTo() {}, moveTo() {}, quadraticCurveTo() {},
  restore() {}, save() {}, scale() {}, setTransform() {}, stroke() {},
  createLinearGradient: () => ({ addColorStop() {} }),
  fillStyle: '', globalAlpha: 1, lineWidth: 1, shadowBlur: 0, shadowColor: '', strokeStyle: '',
})) as unknown as typeof HTMLCanvasElement.prototype.getContext;
