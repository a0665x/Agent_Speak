import { describe, expect, it, vi } from 'vitest';

import { ClipScheduler } from '../../../../AI_Avatar/frontend/controllers/ClipScheduler';
import { VisemeController, VisemeUnavailableError } from '../../../../AI_Avatar/frontend/controllers/VisemeController';
import type { AvatarManifest } from '../../../../AI_Avatar/frontend/types/avatar';

function manifest(): AvatarManifest {
  const states = [
    'idle',
    'listening',
    'thinking',
    'speaking',
    'happy',
    'error',
  ] as const;
  return {
    version: '4.0',
    character: 'Henry',
    viewport: { width: 512, height: 512, anchor_x: 0.5, anchor_y: 0.92 },
    transition_frame_id: 'henry_s0',
    frames: Object.fromEntries([
      ['henry_s0', { src: 'assets/clips/shared/henry_s0.png', sha256: 'a'.repeat(64) }],
      ...states.map((state) => [
        `${state}_001`,
        { src: `assets/clips/${state}/${state}_001.png`, sha256: 'b'.repeat(64) },
      ]),
    ]),
    clips: Object.fromEntries(
      states.map((state) => [
        `${state}_loop`,
        {
          state,
          fps: 12,
          loop: true,
          quality_status: 'approved',
          frames: ['henry_s0', `${state}_001`, 'henry_s0'],
        },
      ]),
    ) as unknown as AvatarManifest['clips'],
  };
}

describe('avatar loop scheduler', () => {
  it('waits for the final shared S0 before switching', () => {
    const scheduler = new ClipScheduler(manifest(), 'idle');

    scheduler.select('listening');
    expect(scheduler.snapshot()).toMatchObject({
      playingState: 'idle',
      pendingState: 'listening',
    });

    scheduler.advanceToFrame('idle_001');
    expect(scheduler.snapshot().playingState).toBe('idle');

    scheduler.advanceToFrame('henry_s0', { loopComplete: true });
    expect(scheduler.snapshot()).toMatchObject({
      playingState: 'listening',
      pendingState: null,
      frameIndex: 0,
    });
  });

  it('retains only the latest selection', () => {
    const scheduler = new ClipScheduler(manifest(), 'idle');

    scheduler.select('listening');
    scheduler.select('thinking');
    scheduler.select('speaking');

    expect(scheduler.snapshot().pendingState).toBe('speaking');
  });

  it('does not restart the active state', () => {
    const scheduler = new ClipScheduler(manifest(), 'idle');
    const selected = vi.fn();
    scheduler.events.on('state.selected', selected);

    expect(scheduler.select('idle')).toBe(false);
    expect(scheduler.snapshot().pendingState).toBeNull();
    expect(selected).not.toHaveBeenCalled();
  });

  it('keeps playing when a target state is unavailable', () => {
    const scheduler = new ClipScheduler(manifest(), 'idle');
    scheduler.setStateAvailable('listening', false);

    expect(scheduler.select('listening')).toBe(false);
    expect(scheduler.snapshot()).toMatchObject({
      playingState: 'idle',
      pendingState: null,
    });
  });

  it('keeps the deferred viseme boundary explicit', () => {
    const visemes = new VisemeController(false);

    expect(() => visemes.setViseme('AA')).toThrow(VisemeUnavailableError);
  });
});
