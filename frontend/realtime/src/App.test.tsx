import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { App } from './App';

test('renders the disabled realtime start control', () => {
  render(<App />);
  expect(screen.getByRole('button', { name: /開始即時聆聽/ })).toBeDisabled();
  expect(screen.getByRole('heading', { name: /Speak\. See it flow\./ })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Realtime processing' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'ASR text relationships' })).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(5);
});

test('reduced motion keeps ambient status textual and static', () => {
  render(<App forceReducedMotion />);
  expect(screen.getByTestId('ambient-waves')).toHaveAttribute('data-animated', 'false');
  expect(screen.getByText(/尚未檢查 Zone Vibe 100/)).toBeInTheDocument();
});
