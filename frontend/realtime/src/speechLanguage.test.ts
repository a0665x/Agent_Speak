import { beforeEach, expect, test } from 'vitest';
import {
  SPEECH_LANGUAGE_STORAGE_KEY,
  defaultSpeechLanguage,
  readSpeechLanguage,
  writeSpeechLanguage,
} from './speechLanguage';

beforeEach(() => localStorage.clear());

test('defaults spoken language from the presentation locale without an override', () => {
  expect(defaultSpeechLanguage('en')).toBe('en');
  expect(defaultSpeechLanguage('zh-TW')).toBe('zh-TW');
  expect(defaultSpeechLanguage('ja')).toBe('ja');
  expect(defaultSpeechLanguage('ko')).toBe('ko');
  expect(readSpeechLanguage('ja')).toEqual({ value: 'ja', overridden: false });
});

test('stores an explicit override independently and preserves auto detection', () => {
  writeSpeechLanguage('auto');
  expect(localStorage.getItem(SPEECH_LANGUAGE_STORAGE_KEY)).toBe('auto');
  expect(readSpeechLanguage('zh-TW')).toEqual({ value: 'auto', overridden: true });
});

test('ignores corrupt stored speech language values', () => {
  localStorage.setItem(SPEECH_LANGUAGE_STORAGE_KEY, 'fr');
  expect(readSpeechLanguage('ko')).toEqual({ value: 'ko', overridden: false });
});
