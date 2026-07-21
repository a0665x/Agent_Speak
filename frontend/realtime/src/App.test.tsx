import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { App } from './App';
import { I18nProvider, type Locale } from './i18n';

function renderApp(locale: Locale = 'en') {
  return render(<I18nProvider initialLocale={locale}><App /></I18nProvider>);
}

test('renders the disabled realtime start control', () => {
  renderApp();
  expect(screen.getByRole('button', { name: /Start realtime listening/ })).toBeDisabled();
  expect(screen.getByRole('heading', { name: /Speak\. See it flow\./ })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Realtime processing' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'ASR text relationships' })).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(5);
});

test('reduced motion keeps ambient status textual and static', () => {
  render(<I18nProvider initialLocale="en"><App forceReducedMotion /></I18nProvider>);
  expect(screen.getByTestId('ambient-waves')).toHaveAttribute('data-animated', 'false');
  expect(screen.getByText(/Zone Vibe 100 input and output not checked/)).toBeInTheDocument();
});

test('changes the complete realtime surface language from the navigation selector', () => {
  renderApp();
  const selector = screen.getByRole('combobox', { name: 'Language' });
  fireEvent.change(selector, { target: { value: 'ja' } });
  expect(screen.getByRole('heading', { name: '話す。流れが見える。' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Realtime listening を開始' })).toBeDisabled();
  expect(screen.getByRole('heading', { name: 'ASR テキストの関係' })).toBeInTheDocument();
});
