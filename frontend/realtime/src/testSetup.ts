import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(cleanup);

HTMLCanvasElement.prototype.getContext = (() => ({
  beginPath() {}, clearRect() {}, closePath() {}, lineTo() {}, moveTo() {}, scale() {}, setTransform() {}, stroke() {},
  strokeStyle: '', lineWidth: 1
})) as unknown as typeof HTMLCanvasElement.prototype.getContext;
