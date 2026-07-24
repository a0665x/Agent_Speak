import { act, fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import type { LoadedAvatarAssets } from '../../../../AI_Avatar/frontend/types/avatar';
import { App } from './App';
import { parseManifest } from './manifest';

const STATES = [
  'idle',
  'listening',
  'thinking',
  'speaking',
  'happy',
  'error',
] as const;

function readyAssets(): LoadedAvatarAssets {
  const frames = Object.fromEntries([
    ['henry_s0', { src: 'assets/clips/shared/henry_s0.png', sha256: 'a'.repeat(64) }],
    ...STATES.map((state) => [
      `${state}_001`,
      { src: `assets/clips/${state}/${state}_001.png`, sha256: 'b'.repeat(64) },
    ]),
  ]);
  const manifest = parseManifest({
    version: '4.0',
    character: 'Henry',
    viewport: { width: 512, height: 512, anchor_x: 0.5, anchor_y: 0.92 },
    transition_frame_id: 'henry_s0',
    frames,
    clips: Object.fromEntries(
      STATES.map((state) => [
        `${state}_loop`,
        {
          state,
          fps: 12,
          loop: true,
          quality_status: 'approved',
          frames: ['henry_s0', `${state}_001`, 'henry_s0'],
        },
      ]),
    ),
  });
  return {
    manifest,
    preload: {
      ready: true,
      loaded: Object.keys(frames).length,
      images: new Map(
        Object.keys(frames).map((frameId) => [frameId, new Image()]),
      ),
    },
  };
}

it('disables state controls until every clip is ready', async () => {
  let resolve!: (assets: LoadedAvatarAssets) => void;
  const pending = new Promise<LoadedAvatarAssets>((done) => {
    resolve = done;
  });
  render(<App manifestLoader={() => pending} />);

  expect(screen.getByRole('button', { name: 'Listening' })).toBeDisabled();
  await act(async () => resolve(readyAssets()));

  expect(await screen.findByText('Assets Ready')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Listening' })).toBeEnabled();
});

it('shows the active loop and only the latest queued state', async () => {
  render(<App manifestLoader={async () => readyAssets()} />);
  await screen.findByText('Assets Ready');

  fireEvent.click(screen.getByRole('button', { name: 'Listening' }));
  fireEvent.click(screen.getByRole('button', { name: 'Thinking' }));

  expect(screen.getByText('Playing: Idle')).toBeVisible();
  expect(screen.getByText('Queued: Thinking')).toBeVisible();
});

it('never requests a microphone or speaker device', async () => {
  const getUserMedia = vi.fn();
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  });

  render(<App manifestLoader={async () => readyAssets()} />);
  await screen.findByText('Assets Ready');

  expect(getUserMedia).not.toHaveBeenCalled();
});
