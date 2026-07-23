export interface GifSpriteRendererOptions { width: number; height: number; }

export class GifSpriteRenderer {
  constructor(private options: GifSpriteRendererOptions) {}
  preload(_src: string): Promise<void> { return Promise.resolve(); }
  show(_src: string): void {}
  reset(): void {}
}
