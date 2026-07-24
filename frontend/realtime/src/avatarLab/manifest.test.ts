import { describe, expect, it, vi } from 'vitest';

import { parseManifest, preloadManifest } from './manifest';

const STATES = [
  'idle',
  'listening',
  'thinking',
  'speaking',
  'happy',
  'error',
] as const;

function fixtureManifest(): Record<string, unknown> {
  const frames: Record<string, { src: string; sha256: string }> = {
    henry_s0: {
      src: 'assets/clips/shared/henry_s0.png',
      sha256: 'a'.repeat(64),
    },
  };
  const clips: Record<string, unknown> = {};
  for (const state of STATES) {
    const frameId = `${state}_001`;
    frames[frameId] = {
      src: `assets/clips/${state}/${frameId}.png`,
      sha256: 'b'.repeat(64),
    };
    clips[`${state}_loop`] = {
      state,
      fps: 12,
      loop: true,
      quality_status: 'approved',
      frames: ['henry_s0', frameId, 'henry_s0'],
    };
  }
  return {
    version: '4.0',
    character: 'Henry',
    viewport: { width: 512, height: 512, anchor_x: 0.5, anchor_y: 0.92 },
    transition_frame_id: 'henry_s0',
    frames,
    clips,
  };
}

describe('avatar manifest', () => {
  it('rejects a clip whose boundaries are not the shared S0', () => {
    const payload = fixtureManifest();
    const clips = payload.clips as Record<string, { frames: string[] }>;
    clips.idle_loop.frames[clips.idle_loop.frames.length - 1] = 'idle_001';

    expect(() => parseManifest(payload)).toThrow(/shared transition frame/);
  });

  it('rejects a frame path that can escape the avatar asset root', () => {
    const payload = fixtureManifest();
    const frames = payload.frames as Record<string, { src: string }>;
    frames.idle_001.src = '../private.png';

    expect(() => parseManifest(payload)).toThrow(/project-relative asset path/);
  });

  it('preloads every unique frame before reporting ready', async () => {
    const manifest = parseManifest(fixtureManifest());
    const load = vi.fn().mockResolvedValue(undefined);

    const result = await preloadManifest(manifest, load);

    expect(load).toHaveBeenCalledTimes(7);
    expect(result.ready).toBe(true);
    expect(result.loaded).toBe(7);
  });

  it('does not report ready when any frame fails to decode', async () => {
    const manifest = parseManifest(fixtureManifest());
    const load = vi.fn(async (src: string) => {
      if (src.includes('thinking')) {
        throw new Error('decode failed');
      }
    });

    await expect(preloadManifest(manifest, load)).rejects.toThrow(
      /thinking.*decode failed/,
    );
  });
});
