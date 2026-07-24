import { EventBus, type AvatarEvents } from '../events/EventBus';

export interface RendererViewport {
  width: number;
  height: number;
}

export type FrameProvider = (timestamp: number) => string | null;

export class PngSequenceRenderer {
  readonly events = new EventBus<AvatarEvents>();
  private readonly context: CanvasRenderingContext2D;
  private readonly images = new Map<string, HTMLImageElement>();
  private animationFrame: number | null = null;
  private provider: FrameProvider | null = null;
  private paused = false;
  private disposed = false;
  private lastDrawnFrame: string | null = null;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly viewport: RendererViewport,
  ) {
    if (viewport.width <= 0 || viewport.height <= 0) {
      throw new Error('renderer viewport must be positive');
    }
    const context = canvas.getContext('2d');
    if (!context) {
      throw new Error('Canvas 2D is unavailable');
    }
    this.context = context;
    this.canvas.width = viewport.width;
    this.canvas.height = viewport.height;
  }

  get lastFrameId(): string | null {
    return this.lastDrawnFrame;
  }

  preload(images: ReadonlyMap<string, HTMLImageElement>): void {
    this.assertUsable();
    for (const [frameId, image] of images) {
      this.images.set(frameId, image);
    }
  }

  draw(frameId: string): void {
    this.assertUsable();
    const image = this.images.get(frameId);
    if (!image) {
      throw new Error(`frame ${frameId} was not preloaded`);
    }
    let saved = false;
    try {
      this.context.save();
      saved = true;
      this.context.globalCompositeOperation = 'copy';
      this.context.drawImage(
        image,
        0,
        0,
        this.viewport.width,
        this.viewport.height,
      );
      this.lastDrawnFrame = frameId;
    } catch (cause) {
      const error = cause instanceof Error ? cause : new Error(String(cause));
      this.events.emit('renderer.failed', { error });
      throw error;
    } finally {
      if (saved) {
        this.context.restore();
      }
    }
  }

  start(provider: FrameProvider): void {
    this.assertUsable();
    this.stopAnimationFrame();
    this.provider = provider;
    this.paused = false;
    this.schedule();
  }

  pause(): void {
    this.paused = true;
    this.stopAnimationFrame();
  }

  resume(): void {
    this.assertUsable();
    if (!this.provider || !this.paused) {
      return;
    }
    this.paused = false;
    this.schedule();
  }

  restart(frameId: string): void {
    this.draw(frameId);
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.stopAnimationFrame();
    this.disposed = true;
    this.images.clear();
    this.events.clear();
  }

  private schedule(): void {
    if (this.paused || this.disposed || !this.provider) {
      return;
    }
    this.animationFrame = window.requestAnimationFrame((timestamp) => {
      this.animationFrame = null;
      if (!this.paused && this.provider) {
        const frameId = this.provider(timestamp);
        if (frameId && frameId !== this.lastDrawnFrame) {
          this.draw(frameId);
        }
      }
      this.schedule();
    });
  }

  private stopAnimationFrame(): void {
    if (this.animationFrame !== null) {
      window.cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
  }

  private assertUsable(): void {
    if (this.disposed) {
      throw new Error('renderer has been disposed');
    }
  }
}
