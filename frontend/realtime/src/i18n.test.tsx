import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import {
  I18nProvider,
  SUPPORTED_LOCALES,
  localizedHref,
  messages,
  resolveLocale,
  useI18n,
} from './i18n';

test('resolves query before storage and defaults invalid queries to English', () => {
  expect(resolveLocale('?lang=ja', 'zh-TW')).toBe('ja');
  expect(resolveLocale('', 'ko')).toBe('ko');
  expect(resolveLocale('?lang=unsupported', 'zh-TW')).toBe('en');
  expect(resolveLocale('', null)).toBe('en');
});

test('keeps every realtime locale catalog complete', () => {
  const keys = Object.keys(messages.en);
  for (const locale of SUPPORTED_LOCALES) {
    expect(Object.keys(messages[locale])).toEqual(keys);
    expect(Object.values(messages[locale]).every(value => value.length > 0)).toBe(true);
  }
});

test('localizes internal navigation links', () => {
  expect(localizedHref('/', 'ko')).toBe('/?lang=ko');
  expect(localizedHref('/docs?view=full', 'ja')).toBe('/docs?view=full&lang=ja');
});

function Probe() {
  const { locale, setLocale, t } = useI18n();
  return <>
    <output>{locale}:{t('hero.title')}</output>
    <button type="button" onClick={() => setLocale('zh-TW')}>change</button>
  </>;
}

test('provider updates the document language and persists explicit selection', () => {
  localStorage.clear();
  render(<I18nProvider initialLocale="ja"><Probe /></I18nProvider>);
  expect(document.documentElement.lang).toBe('ja');
  expect(screen.getByText('ja:話す。流れが見える。')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'change' }));
  expect(document.documentElement.lang).toBe('zh-TW');
  expect(localStorage.getItem('agent-speak-locale')).toBe('zh-TW');
});
