import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { App } from './App';

test('renders the disabled realtime start control', () => {
  render(<App />);
  expect(screen.getByRole('button', { name: /開始即時聆聽/ })).toBeDisabled();
});

test('reduced motion keeps ambient status textual and static', () => {
  render(<App forceReducedMotion />);
  expect(screen.getByTestId('ambient-waves')).toHaveAttribute('data-animated', 'false');
  expect(screen.getByText(/尚未檢查 Zone Vibe 100/)).toBeInTheDocument();
});
