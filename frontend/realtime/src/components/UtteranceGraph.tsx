import { useMemo, useState } from 'react';
import type { TranscriptRow } from '../state/reducer';
import { buildTextGraph } from '../graph/textGraph';

export function UtteranceGraph({ rows, completedUtteranceIds }: {
  rows: TranscriptRow[];
  completedUtteranceIds: string[];
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const graph = useMemo(() => {
    const rowById = new Map(rows.map(row => [row.utteranceId, row]));
    return buildTextGraph(completedUtteranceIds.flatMap(utteranceId => {
      const row = rowById.get(utteranceId);
      return row?.text ? [{ utteranceId, text: row.text }] : [];
    }));
  }, [rows, completedUtteranceIds]);
  const nodeById = new Map(graph.nodes.map(node => [node.utteranceId, node]));
  const hovered = hoveredId ? nodeById.get(hoveredId) : undefined;

  return (
    <section className="utterance-graph" aria-labelledby="utterance-graph-title">
      <header className="graph-heading">
        <div>
          <p className="eyebrow">UTTERANCE GRAPH</p>
          <h2 id="utterance-graph-title">ASR text relationships</h2>
          <p>每個 endpoint 是一段文字；實線是時間，虛線是 local text similarity。</p>
        </div>
        <div className="graph-legend" aria-label="Graph legend">
          <span><i className="timeline-key" />時間順序</span>
          <span><i className="similarity-key" />文字相似</span>
        </div>
      </header>
      {graph.nodes.length === 0 ? (
        <div className="graph-empty"><span aria-hidden="true">⌁</span><p>完成第一段校正後，節點會出現在這裡。</p></div>
      ) : (
        <svg className="graph-canvas" viewBox="0 0 1000 430" role="img" aria-label="已完成語音片段的文字關係圖">
          <g className="graph-edges" aria-hidden="true">
            {graph.edges.map((edge, index) => {
              const source = nodeById.get(edge.source);
              const target = nodeById.get(edge.target);
              if (!source || !target) return null;
              return <line className={`graph-edge ${edge.kind}`} key={`${edge.kind}-${edge.source}-${edge.target}-${index}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />;
            })}
          </g>
          <g className="graph-nodes">
            {graph.nodes.map((node, index) => {
              const recencyClass = node.recency === 0 ? 'new' : 'history';
              return (
                <g
                  className={`graph-node ${recencyClass}${hoveredId === node.utteranceId ? ' hovered' : ''}`}
                  data-testid={`graph-node-${node.utteranceId}`}
                  key={node.utteranceId}
                  transform={`translate(${node.x} ${node.y})`}
                >
                  <circle
                    className="node-hit"
                    data-testid={`node-hit-${node.utteranceId}`}
                    r="36"
                    onPointerEnter={() => setHoveredId(node.utteranceId)}
                    onPointerLeave={() => setHoveredId(null)}
                    aria-label={`語音片段 ${index + 1}`}
                  />
                  <g className="node-visual" data-testid={`node-visual-${node.utteranceId}`} aria-hidden="true">
                    <circle className="node-halo" r="34" />
                    <circle className="node-core" r={node.recency === 0 ? 22 : 16} />
                    <text textAnchor="middle" dominantBaseline="central">{index + 1}</text>
                  </g>
                </g>
              );
            })}
          </g>
        </svg>
      )}
      {hovered && (
        <div
          className="graph-tooltip"
          role="tooltip"
          style={{ left: `${hovered.x / 10}%`, top: `${Math.max(22, hovered.y / 4.3)}%` }}
        >
          <span>&lt;text&gt;</span>{hovered.text}
        </div>
      )}
    </section>
  );
}
