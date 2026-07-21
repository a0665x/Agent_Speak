import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { I18nProvider } from '../i18n';
import { AudioStage } from './AudioStage';
import { DeviceGate } from './DeviceGate';
import { TranscriptPanel } from './TranscriptPanel';

test('localizes device, audio, and transcript empty states in Traditional Chinese', () => {
  render(
    <I18nProvider initialLocale="zh-TW">
      <DeviceGate gate={{ ready: false, reason: 'unchecked' }} />
      <AudioStage samples={[]} state="ready" />
      <TranscriptPanel rows={[]} />
    </I18nProvider>
  );
  expect(screen.getByText('麥克風尚未確認')).toBeInTheDocument();
  expect(screen.getByText('等待裝置')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '逐句辨識文字' })).toBeInTheDocument();
});

test('localizes transcript status while preserving recognized text', () => {
  render(
    <I18nProvider initialLocale="ja">
      <TranscriptPanel rows={[{ utteranceId: 'u-1', text: 'recognised content', status: 'partial' }]} />
    </I18nProvider>
  );
  expect(screen.getByText('recognised content')).toBeInTheDocument();
  expect(screen.getByText('暫定認識')).toBeInTheDocument();
});
