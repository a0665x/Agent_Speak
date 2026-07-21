import { expect, test } from 'vitest';
import { buildTextGraph, cosineSimilarity, embedText } from './textGraph';

const rows = (count: number) => Array.from({ length: count }, (_, index) => ({
  utteranceId: `u-${index + 1}`,
  text: `第 ${index + 1} 段即時語音辨識文字`,
}));

test('produces deterministic normalized feature vectors', () => {
  const first = embedText('即時語音辨識');
  const second = embedText('即時語音辨識');
  expect(first).toEqual(second);
  expect(Math.hypot(...first)).toBeCloseTo(1, 5);
  expect(cosineSimilarity(first, second)).toBeCloseTo(1, 5);
});

test('keeps coordinates stable and bounds the graph', () => {
  const first = buildTextGraph(rows(3), 24);
  const next = buildTextGraph(rows(4), 24);
  expect(next.nodes.slice(0, 3).map(node => [node.x, node.y])).toEqual(
    first.nodes.map(node => [node.x, node.y])
  );
  expect(buildTextGraph(rows(30), 24).nodes).toHaveLength(24);
});

test('adds chronological edges and only thresholded similarity edges', () => {
  const graph = buildTextGraph([
    { utteranceId: 'a', text: '即時語音辨識顯示文字' },
    { utteranceId: 'b', text: '今天台北天氣很好' },
    { utteranceId: 'c', text: '即時語音轉成辨識文字' },
  ], 24, .42);
  expect(graph.edges.filter(edge => edge.kind === 'timeline')).toHaveLength(graph.nodes.length - 1);
  expect(graph.edges.filter(edge => edge.kind === 'similarity').every(edge => edge.score >= .42)).toBe(true);
  expect(graph.edges.some(edge => edge.kind === 'similarity' && edge.source === 'a' && edge.target === 'c')).toBe(true);
});

test('empty text creates a safe zero vector and finite graph coordinates', () => {
  expect(embedText('')).toEqual(Array.from({ length: 96 }, () => 0));
  const graph = buildTextGraph([{ utteranceId: 'empty', text: '' }]);
  expect(Number.isFinite(graph.nodes[0].x)).toBe(true);
  expect(Number.isFinite(graph.nodes[0].y)).toBe(true);
});
