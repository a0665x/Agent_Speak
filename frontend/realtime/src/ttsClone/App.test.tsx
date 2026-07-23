import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App, type CloneStudioDependencies } from './App';
import type { ResourceOperation } from '../resources';

function resourceOperation(
  phase: ResourceOperation['phase'],
): ResourceOperation {
  return {
    id: 'op_0123456789abcdef',
    action: 'reset',
    target: 'tts',
    phase,
    created_at: '2026-07-23T00:00:00Z',
    updated_at: '2026-07-23T00:00:01Z',
    error_code: null,
    operator_hint: null,
  };
}

function readyDependencies(overrides: Partial<CloneStudioDependencies> = {}): CloneStudioDependencies {
  let generated: Blob | undefined;
  let generatedUrl: string | undefined;
  return {
    getStatus: vi.fn().mockResolvedValue({
      gpuMode: 'tts',
      accelerator: 'nvidia',
      state: 'ready',
      model: 'voxcpm2',
      device: 'cuda',
      ready: true,
    }),
    checkDevices: vi.fn().mockResolvedValue({
      ready: true,
      input: { deviceId: 'mic', kind: 'audioinput', label: 'Mic', groupId: '', toJSON() {} },
      output: { deviceId: 'speaker', kind: 'audiooutput', label: 'Speaker', groupId: '', toJSON() {} },
      reason: 'ready',
    }),
    validate: vi.fn().mockResolvedValue({
      durationSeconds: 10,
      rms: 0.2,
      peak: 0.4,
      voicedRatio: 0.9,
      quality: 'good',
    }),
    synthesize: vi.fn().mockResolvedValue(new Blob(['wav'], { type: 'audio/wav' })),
    resetResource: vi.fn().mockResolvedValue(resourceOperation('queued')),
    waitForResourceOperation: vi.fn().mockImplementation(async (
      _id: string,
      onPhase: (phase: ResourceOperation['phase']) => void,
    ) => {
      for (const phase of ['releasing', 'starting', 'warming', 'ready'] as const) {
        onPhase(phase);
      }
      return resourceOperation('ready');
    }),
    recorder: {
      state: 'idle',
      start: vi.fn().mockResolvedValue(undefined),
      stop: vi.fn().mockResolvedValue(new Blob(['reference'], { type: 'audio/wav' })),
      discard: vi.fn().mockResolvedValue(undefined),
      subscribeAmplitude: vi.fn(() => () => undefined),
    },
    audioStore: {
      reference: undefined,
      generated,
      referenceUrl: undefined,
      generatedUrl,
      setReference: vi.fn(),
      clearReference: vi.fn(),
      setGenerated: vi.fn(blob => {
        generated = blob;
        generatedUrl = 'blob:generated';
      }),
      clearGenerated: vi.fn(),
      dispose: vi.fn(),
    },
    playback: {
      playing: false,
      setSource: vi.fn(),
      play: vi.fn().mockResolvedValue(undefined),
      stop: vi.fn(),
      subscribeAmplitude: vi.fn(() => () => undefined),
      subscribeEnded: vi.fn(() => () => undefined),
      dispose: vi.fn(),
    },
    watchDevices: vi.fn(() => () => undefined),
    ...overrides,
  };
}

describe('TTS Clone Studio', () => {
  it('resets TTS and leaves audio actions explicit after readiness', async () => {
    const loading = {
      gpuMode: 'tts' as const,
      accelerator: 'nvidia' as const,
      state: 'loading' as const,
      model: 'voxcpm2' as const,
      device: 'cuda',
      ready: false,
    };
    const ready = { ...loading, state: 'ready' as const, ready: true };
    const getStatus = vi.fn()
      .mockResolvedValueOnce(loading)
      .mockResolvedValue(ready);
    const deps = readyDependencies({ getStatus });
    render(<App dependencies={deps} />);

    fireEvent.click(screen.getByRole('button', {
      name: 'Reset TTS resources',
    }));

    await waitFor(() => expect(deps.resetResource).toHaveBeenCalledWith(
      'tts',
    ));
    await waitFor(() => expect(screen.getAllByText(
      'TTS resources ready',
    ).length).toBeGreaterThan(0));
    expect(deps.checkDevices).not.toHaveBeenCalled();
    expect(deps.synthesize).not.toHaveBeenCalled();
    expect(deps.playback.play).not.toHaveBeenCalled();
    expect(screen.getByRole('button', {
      name: 'Start recording',
    })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
    await waitFor(() => expect(screen.getByRole('button', {
      name: 'Start recording',
    })).toBeEnabled());
  });

  it('confirms and discards active capture before resetting TTS', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const deps = readyDependencies();
    render(<App dependencies={deps} />);
    await waitFor(() => expect(deps.getStatus).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
    await waitFor(() => expect(screen.getByRole('button', {
      name: 'Start recording',
    })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Start recording' }));
    await waitFor(() => expect(deps.recorder.start).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', {
      name: 'Reset TTS resources',
    }));

    await waitFor(() => expect(deps.recorder.discard).toHaveBeenCalled());
    expect(confirm).toHaveBeenCalledWith(
      'An audio action is active. Stop it and reset TTS resources?',
    );
    expect(vi.mocked(deps.recorder.discard).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(deps.resetResource).mock.invocationCallOrder[0],
    );
    confirm.mockRestore();
  });

  it('keeps Voice Clone and TTS Play freely switchable', async () => {
    render(<App dependencies={readyDependencies()} />);

    fireEvent.click(screen.getByRole('tab', { name: 'TTS Play' }));
    expect(screen.getByRole('tabpanel', { name: 'TTS Play' })).toBeVisible();
    fireEvent.click(screen.getByRole('tab', { name: 'Voice Clone' }));
    expect(screen.getByRole('tabpanel', { name: 'Voice Clone' })).toBeVisible();
  });

  it('gates controls until devices are explicitly checked', async () => {
    const deps = readyDependencies();
    render(<App dependencies={deps} />);
    await waitFor(() => expect(deps.getStatus).toHaveBeenCalled());

    expect(screen.getByRole('button', { name: 'Start recording' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Start recording' })).toBeEnabled());
  });

  it('requires Generate before Play and never autoplays', async () => {
    const deps = readyDependencies();
    render(<App dependencies={deps} />);
    await waitFor(() => expect(deps.getStatus).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
    await waitFor(() => expect(deps.checkDevices).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('tab', { name: 'TTS Play' }));

    expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Text to speak'), { target: { value: 'Hello' } });
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));

    await waitFor(() => expect(screen.getByRole('button', { name: 'Play' })).toBeEnabled());
    expect(deps.playback.play).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    await waitFor(() => expect(deps.playback.play).toHaveBeenCalledTimes(1));
  });

  it('shows the wrong-mode recovery command', async () => {
    render(<App dependencies={readyDependencies({
      getStatus: vi.fn().mockResolvedValue({
        gpuMode: 'asr',
        accelerator: 'nvidia',
        state: 'stopped',
        model: 'voxcpm2',
        device: 'nvidia',
        ready: false,
        errorCode: 'wrong_gpu_mode',
        operatorHint: './run.sh --tts-up',
      }),
    })} />);

    expect(await screen.findByText('./run.sh --tts-up')).toBeVisible();
  });
});
