import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PngSequenceRenderer } from '../../../../AI_Avatar/frontend/renderers/PngSequenceRenderer';

function setup() {
  const canvas = document.createElement('canvas');
  const context = {
    drawImage: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    globalCompositeOperation: 'source-over',
  } as unknown as CanvasRenderingContext2D;
  vi.spyOn(canvas, 'getContext').mockReturnValue(context);
  const renderer = new PngSequenceRenderer(canvas, {
    width: 512,
    height: 512,
  });
  return { canvas, context, renderer };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('PNG sequence renderer', () => {
  it('keeps the viewport fixed across clips', () => {
    const { canvas, renderer } = setup();
    const images = new Map([
      ['idle', new Image()],
      ['speaking', new Image()],
    ]);
    renderer.preload(images);

    renderer.draw('idle');
    renderer.draw('speaking');

    expect([canvas.width, canvas.height]).toEqual([512, 512]);
  });

  it('never draws an unpreloaded frame', () => {
    const { renderer } = setup();

    expect(() => renderer.draw('missing')).toThrow(/not preloaded/);
  });

  it('retains the last frame and emits when a draw fails', () => {
    const { context, renderer } = setup();
    const good = new Image();
    const broken = new Image();
    renderer.preload(new Map([['good', good], ['broken', broken]]));
    const failed = vi.fn();
    renderer.events.on('renderer.failed', failed);
    renderer.draw('good');
    vi.mocked(context.drawImage).mockImplementationOnce(() => {
      throw new Error('GPU context lost');
    });

    expect(() => renderer.draw('broken')).toThrow(/GPU context lost/);
    expect(renderer.lastFrameId).toBe('good');
    expect(failed).toHaveBeenCalledOnce();
  });

  it('cancels its animation frame when disposed', () => {
    const { renderer } = setup();
    const request = vi
      .spyOn(window, 'requestAnimationFrame')
      .mockReturnValue(42);
    const cancel = vi.spyOn(window, 'cancelAnimationFrame');
    renderer.start(() => null);
    expect(request).toHaveBeenCalled();

    renderer.dispose();

    expect(cancel).toHaveBeenCalledWith(42);
  });
});
