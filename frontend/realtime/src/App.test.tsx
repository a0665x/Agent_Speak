import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { App } from './App';

test('renders the disabled realtime start control', () => {
  render(<App />);
  expect(screen.getByRole('button', { name: /開始即時聆聽/ })).toBeDisabled();
});
