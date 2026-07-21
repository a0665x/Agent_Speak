import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, test } from 'vitest';
import type { TranscriptRow } from '../state/reducer';
import { I18nProvider } from '../i18n';
import { UtteranceGraph } from './UtteranceGraph';

const rows: TranscriptRow[] = [
  { utteranceId: 'u-1', text: '第一段完成校正的文字', status: 'locked' },
  { utteranceId: 'u-2', text: '第二段仍在辨識', status: 'partial' },
];

function graph(completedUtteranceIds: string[], locale: 'en' | 'ko' = 'en', graphRows = rows) {
  return <I18nProvider initialLocale={locale}><UtteranceGraph rows={graphRows} completedUtteranceIds={completedUtteranceIds} /></I18nProvider>;
}

test('renders only completed utterances with layered stable nodes', () => {
  render(graph(['u-1']));
  const node = screen.getByTestId('graph-node-u-1');
  expect(node.getAttribute('transform')).toMatch(/^translate\(/);
  expect(within(node).getByTestId('node-hit-u-1')).toHaveAttribute('r', '36');
  expect(within(node).getByTestId('node-visual-u-1')).not.toHaveAttribute('transform');
  expect(screen.queryByTestId('graph-node-u-2')).not.toBeInTheDocument();
});

test('hover shows corrected text without changing position transform', () => {
  render(graph(['u-1']));
  const node = screen.getByTestId('graph-node-u-1');
  const before = node.getAttribute('transform');
  fireEvent.pointerEnter(screen.getByTestId('node-hit-u-1'));
  expect(screen.getByRole('tooltip')).toHaveTextContent(rows[0].text);
  expect(node).toHaveAttribute('transform', before);
});

test('newest completed node has a stronger recency class than history', () => {
  render(graph(['u-1', 'u-2'], 'en', rows.map(row => ({ ...row, status: 'locked' }))));
  expect(screen.getByTestId('graph-node-u-2')).toHaveClass('new');
  expect(screen.getByTestId('graph-node-u-1')).toHaveClass('history');
});

test('localizes graph explanation, legend, and accessible node label', () => {
  render(graph(['u-1'], 'ko'));
  expect(screen.getByRole('heading', { name: 'ASR 텍스트 관계' })).toBeInTheDocument();
  expect(screen.getByLabelText('음성 segment 1')).toBeInTheDocument();
  expect(screen.getByText('텍스트 유사도')).toBeInTheDocument();
});
