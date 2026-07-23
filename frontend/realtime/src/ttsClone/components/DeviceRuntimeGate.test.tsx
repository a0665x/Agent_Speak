import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DeviceRuntimeGate } from './DeviceRuntimeGate';

describe('device and runtime gate', () => {
  it('shows every prerequisite and recovery command', () => {
    render(
      <DeviceRuntimeGate
        microphone="ready"
        speaker="ready"
        status={{
          gpuMode: 'asr',
          accelerator: 'nvidia',
          state: 'stopped',
          model: 'voxcpm2',
          device: 'nvidia',
          ready: false,
          errorCode: 'wrong_gpu_mode',
          operatorHint: './run.sh --tts-up',
        }}
        hasReference={false}
        labels={{
          microphone: 'Microphone',
          speaker: 'Speaker',
          cuda: 'CUDA',
          worker: 'vLLM-Omni',
          model: 'VoxCPM2',
          reference: 'Reference',
          ready: 'Ready',
          waiting: 'Waiting',
          missing: 'Missing',
        }}
      />,
    );

    for (const label of ['Microphone', 'Speaker', 'CUDA', 'vLLM-Omni', 'VoxCPM2', 'Reference']) {
      expect(screen.getByText(label)).toBeVisible();
    }
    expect(screen.getByText('./run.sh --tts-up')).toBeVisible();
  });
});
