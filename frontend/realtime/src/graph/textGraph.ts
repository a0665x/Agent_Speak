const VECTOR_SIZE = 96;
const DEFAULT_MAX_NODES = 24;
const DEFAULT_SIMILARITY_THRESHOLD = .42;

export type TextGraphInput = {
  utteranceId: string;
  text: string;
};

export type TextGraphNode = TextGraphInput & {
  x: number;
  y: number;
  recency: number;
  vector: number[];
};

export type TextGraphEdge = {
  source: string;
  target: string;
  kind: 'timeline' | 'similarity';
  score: number;
};

export type TextGraph = {
  nodes: TextGraphNode[];
  edges: TextGraphEdge[];
};

export function embedText(text: string): number[] {
  const vector = Array.from({ length: VECTOR_SIZE }, () => 0);
  const tokens = tokenize(text);
  const features = [
    ...tokens.map(token => ({ value: `u:${token}`, weight: 1 })),
    ...tokens.slice(0, -1).map((token, index) => ({ value: `b:${token}|${tokens[index + 1]}`, weight: 1.35 })),
  ];
  for (const feature of features) {
    const hash = hashString(feature.value);
    const index = hash % VECTOR_SIZE;
    const sign = (hash & 0x100) === 0 ? 1 : -1;
    vector[index] += feature.weight * sign;
  }
  const norm = Math.hypot(...vector);
  return norm === 0 ? vector : vector.map(value => value / norm);
}

export function cosineSimilarity(left: number[], right: number[]): number {
  const length = Math.min(left.length, right.length);
  let score = 0;
  for (let index = 0; index < length; index += 1) score += left[index] * right[index];
  return score;
}

export function buildTextGraph(
  input: TextGraphInput[],
  maxNodes = DEFAULT_MAX_NODES,
  similarityThreshold = DEFAULT_SIMILARITY_THRESHOLD,
): TextGraph {
  const bounded = input.slice(-Math.max(1, maxNodes));
  const nodes = bounded.map((row, index) => ({
    ...row,
    ...stableCoordinates(row.utteranceId),
    recency: bounded.length - 1 - index,
    vector: embedText(row.text),
  }));
  const edges: TextGraphEdge[] = [];
  for (let index = 1; index < nodes.length; index += 1) {
    edges.push({ source: nodes[index - 1].utteranceId, target: nodes[index].utteranceId, kind: 'timeline', score: 1 });
  }
  for (let targetIndex = 1; targetIndex < nodes.length; targetIndex += 1) {
    const candidates = nodes.slice(0, targetIndex)
      .map((source, sourceIndex) => ({
        source,
        sourceIndex,
        score: cosineSimilarity(source.vector, nodes[targetIndex].vector),
      }))
      .filter(candidate => candidate.score >= similarityThreshold && candidate.sourceIndex !== targetIndex - 1)
      .sort((left, right) => right.score - left.score)
      .slice(0, 2);
    for (const candidate of candidates) {
      edges.push({
        source: candidate.source.utteranceId,
        target: nodes[targetIndex].utteranceId,
        kind: 'similarity',
        score: candidate.score,
      });
    }
  }
  return { nodes, edges };
}

function tokenize(text: string): string[] {
  const normalized = text.normalize('NFKC').toLocaleLowerCase().trim();
  return normalized.match(/[\p{Script=Han}]|[\p{L}\p{N}_]+/gu) ?? [];
}

function stableCoordinates(id: string): { x: number; y: number } {
  const xHash = hashString(`x:${id}`);
  const yHash = hashString(`y:${id}`);
  return {
    x: 90 + xHash % 820,
    y: 105 + yHash % 220,
  };
}

function hashString(value: string): number {
  let hash = 0x811c9dc5;
  for (const character of value) {
    hash ^= character.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}
