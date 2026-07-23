import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import { ResourceReset } from './ResourceReset';

describe('ResourceReset', () => {
  test('shows progress, prevents duplicate reset, and announces phase', () => {
    const onReset = vi.fn().mockResolvedValue(undefined);
    render(
      <ResourceReset
        label="Reset ASR resources"
        phase="warming"
        busy
        onReset={onReset}
        phaseLabel={phase => phase}
      />,
    );

    const button = screen.getByRole('button', {
      name: 'Reset ASR resources',
    });
    expect(button).toBeDisabled();
    expect(button).toHaveClass('resource-reset__button');
    expect(screen.getByRole('status')).toHaveTextContent('warming');
    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-live',
      'polite',
    );
    expect(onReset).not.toHaveBeenCalled();
  });

  test('confirms, supports native keyboard activation, and blocks duplicates', async () => {
    let release: (() => void) | undefined;
    const onReset = vi.fn(() => new Promise<void>(resolve => {
      release = resolve;
    }));
    const confirmReset = vi.fn().mockResolvedValue(true);
    render(
      <ResourceReset
        label="Reset TTS resources"
        phase={null}
        busy={false}
        confirmReset={confirmReset}
        onReset={onReset}
        phaseLabel={phase => phase}
      />,
    );
    const button = screen.getByRole('button', {
      name: 'Reset TTS resources',
    });

    button.focus();
    fireEvent.keyDown(button, { key: 'Enter' });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect(onReset).toHaveBeenCalledTimes(1));
    expect(confirmReset).toHaveBeenCalledTimes(1);
    release?.();
  });

  test('does not reset when confirmation is declined', async () => {
    const onReset = vi.fn();
    render(
      <ResourceReset
        label="Reset ASR resources"
        phase={null}
        busy={false}
        confirmReset={() => false}
        onReset={onReset}
        phaseLabel={phase => phase}
      />,
    );

    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => expect(onReset).not.toHaveBeenCalled());
  });

  test('shows recovery and reduced-motion semantics without color alone', () => {
    render(
      <ResourceReset
        label="Reset TTS resources"
        phase="failed"
        busy={false}
        error="TTS resources failed"
        recoveryHint="./run.sh --logs tts-worker"
        reducedMotion
        onReset={() => undefined}
        phaseLabel={phase => `Phase: ${phase}`}
      />,
    );

    const control = screen.getByTestId('resource-reset');
    expect(control).toHaveAttribute('data-reduced-motion', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'TTS resources failed',
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      './run.sh --logs tts-worker',
    );
    expect(screen.getByRole('status')).toHaveTextContent('Phase: failed');
  });
});
