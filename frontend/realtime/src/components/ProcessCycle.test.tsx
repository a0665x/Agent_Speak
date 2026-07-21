import { act, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { I18nProvider } from '../i18n';
import { ProcessCycle } from './ProcessCycle';

afterEach(() => vi.useRealTimers());

function cycle(stage: Parameters<typeof ProcessCycle>[0]['stage'], reducedMotion: boolean, locale: 'en' | 'ja' = 'en') {
  return <I18nProvider initialLocale={locale}><ProcessCycle stage={stage} reducedMotion={reducedMotion} /></I18nProvider>;
}

test('keeps the previous stage as a trail while the current stage is active', () => {
  vi.useFakeTimers();
  const view = render(cycle('voice', false));
  view.rerender(cycle('asr', false));
  expect(screen.getByTestId('stage-asr')).toHaveAttribute('data-state', 'active');
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'trail');
  act(() => vi.advanceTimersByTime(1500));
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'idle');
});

test('reduced motion keeps semantic state without trail animation', () => {
  const view = render(cycle('voice', true));
  view.rerender(cycle('asr', true));
  expect(screen.getByTestId('stage-asr')).toHaveAttribute('data-state', 'active');
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'idle');
});

test('renders the five ordered speech processing stages', () => {
  render(cycle('listening', true));
  expect(screen.getAllByRole('listitem')).toHaveLength(5);
  expect(screen.getByText('Listening')).toBeInTheDocument();
  expect(screen.getByText('Voice detected')).toBeInTheDocument();
  expect(screen.getByText('ASR partial')).toBeInTheDocument();
  expect(screen.getByText('Endpoint')).toBeInTheDocument();
  expect(screen.getByText('Correction')).toBeInTheDocument();
});

test('localizes every ordered stage without changing semantic stage keys', () => {
  render(cycle('voice', true, 'ja'));
  expect(screen.getAllByText('音声を検出')).toHaveLength(2);
  expect(screen.getByText('テキスト更新中')).toBeInTheDocument();
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'active');
});
