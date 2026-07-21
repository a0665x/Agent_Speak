import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, test } from 'vitest';
import type { TranscriptRow } from '../state/reducer';
import { UtteranceGraph } from './UtteranceGraph';

const rows: TranscriptRow[] = [
  { utteranceId: 'u-1', text: '第一段完成校正的文字', status: 'locked' },
  { utteranceId: 'u-2', text: '第二段仍在辨識', status: 'partial' },
];

test('renders only completed utterances with layered stable nodes', () => {
  render(<UtteranceGraph rows={rows} completedUtteranceIds={['u-1']} />);
  const node = screen.getByTestId('graph-node-u-1');
  expect(node.getAttribute('transform')).toMatch(/^translate\(/);
  expect(within(node).getByTestId('node-hit-u-1')).toHaveAttribute('r', '36');
  expect(within(node).getByTestId('node-visual-u-1')).not.toHaveAttribute('transform');
  expect(screen.queryByTestId('graph-node-u-2')).not.toBeInTheDocument();
});

test('hover shows corrected text without changing position transform', () => {
  render(<UtteranceGraph rows={rows} completedUtteranceIds={['u-1']} />);
  const node = screen.getByTestId('graph-node-u-1');
  const before = node.getAttribute('transform');
  fireEvent.pointerEnter(screen.getByTestId('node-hit-u-1'));
  expect(screen.getByRole('tooltip')).toHaveTextContent(rows[0].text);
  expect(node).toHaveAttribute('transform', before);
});

test('newest completed node has a stronger recency class than history', () => {
  render(<UtteranceGraph rows={rows.map(row => ({ ...row, status: 'locked' }))} completedUtteranceIds={['u-1', 'u-2']} />);
  expect(screen.getByTestId('graph-node-u-2')).toHaveClass('new');
  expect(screen.getByTestId('graph-node-u-1')).toHaveClass('history');
});
