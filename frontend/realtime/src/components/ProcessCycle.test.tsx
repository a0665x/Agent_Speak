import { act, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { ProcessCycle } from './ProcessCycle';

afterEach(() => vi.useRealTimers());

test('keeps the previous stage as a trail while the current stage is active', () => {
  vi.useFakeTimers();
  const view = render(<ProcessCycle stage="voice" reducedMotion={false} />);
  view.rerender(<ProcessCycle stage="asr" reducedMotion={false} />);
  expect(screen.getByTestId('stage-asr')).toHaveAttribute('data-state', 'active');
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'trail');
  act(() => vi.advanceTimersByTime(1500));
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'idle');
});

test('reduced motion keeps semantic state without trail animation', () => {
  const view = render(<ProcessCycle stage="voice" reducedMotion />);
  view.rerender(<ProcessCycle stage="asr" reducedMotion />);
  expect(screen.getByTestId('stage-asr')).toHaveAttribute('data-state', 'active');
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'idle');
});

test('renders the five ordered speech processing stages', () => {
  render(<ProcessCycle stage="listening" reducedMotion />);
  expect(screen.getAllByRole('listitem')).toHaveLength(5);
  expect(screen.getByText('Listening')).toBeInTheDocument();
  expect(screen.getByText('Voice detected')).toBeInTheDocument();
  expect(screen.getByText('ASR partial')).toBeInTheDocument();
  expect(screen.getByText('Endpoint')).toBeInTheDocument();
  expect(screen.getByText('Correction')).toBeInTheDocument();
});
