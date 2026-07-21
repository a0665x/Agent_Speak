import type { Locale } from './i18n';

export const SPEECH_LANGUAGES = ['auto', 'en', 'zh-TW', 'ja', 'ko'] as const;
export type SpeechLanguage = typeof SPEECH_LANGUAGES[number];
export const SPEECH_LANGUAGE_STORAGE_KEY = 'agent-speak-speech-language';

export function defaultSpeechLanguage(locale: Locale): SpeechLanguage {
  return locale;
}

export function parseSpeechLanguage(value: string | null): SpeechLanguage | null {
  return SPEECH_LANGUAGES.includes(value as SpeechLanguage) ? value as SpeechLanguage : null;
}

export function readSpeechLanguage(locale: Locale): { value: SpeechLanguage; overridden: boolean } {
  let stored: string | null = null;
  try { stored = localStorage.getItem(SPEECH_LANGUAGE_STORAGE_KEY); } catch { /* Use locale default. */ }
  const value = parseSpeechLanguage(stored);
  return value ? { value, overridden: true } : { value: defaultSpeechLanguage(locale), overridden: false };
}

export function writeSpeechLanguage(value: SpeechLanguage): void {
  try { localStorage.setItem(SPEECH_LANGUAGE_STORAGE_KEY, value); } catch { /* Keep in-memory selection. */ }
}

export function speechLanguageName(value: SpeechLanguage, autoLabel = 'Auto detect'): string {
  if (value === 'auto') return autoLabel;
  return ({ en: 'English', 'zh-TW': '繁體中文', ja: '日本語', ko: '한국어' })[value];
}
