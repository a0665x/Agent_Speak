import { describe, expect, it } from 'vitest';
import { CATALOGS, resolveLocale } from './i18n';

describe('TTS clone localization', () => {
  it('keeps exact catalog parity in all four locales', () => {
    const english = Object.keys(CATALOGS.en).sort();
    expect(Object.keys(CATALOGS['zh-TW']).sort()).toEqual(english);
    expect(Object.keys(CATALOGS.ja).sort()).toEqual(english);
    expect(Object.keys(CATALOGS.ko).sort()).toEqual(english);
  });

  it('defaults to English and accepts query or saved locale', () => {
    expect(resolveLocale('', null)).toBe('en');
    expect(resolveLocale('?lang=zh-TW', 'en')).toBe('zh-TW');
    expect(resolveLocale('', 'ja')).toBe('ja');
    expect(resolveLocale('?lang=invalid', 'ko')).toBe('ko');
  });

  it('localizes every TTS resource reset state', () => {
    for (const locale of ['en', 'zh-TW', 'ja', 'ko'] as const) {
      expect(CATALOGS[locale].resourceReset).toBeTruthy();
      expect(CATALOGS[locale].resourceConfirmActive).toBeTruthy();
      expect(CATALOGS[locale].resourcePhaseWarming).toBeTruthy();
      expect(CATALOGS[locale].resourceReconnecting).toBeTruthy();
      expect(CATALOGS[locale].resourceFailed).toBeTruthy();
      expect(CATALOGS[locale].resourceRecovery).toBeTruthy();
    }
  });
});
