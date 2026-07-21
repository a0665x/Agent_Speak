import { useMemo, useState } from 'react';
import type { TranscriptRow } from '../state/reducer';
import { buildTextGraph } from '../graph/textGraph';
import { useI18n } from '../i18n';

export function UtteranceGraph({ rows, completedUtteranceIds }: {
  rows: TranscriptRow[];
  completedUtteranceIds: string[];
}) {
  const { t } = useI18n();
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
          <p className="eyebrow">{t('graph.eyebrow')}</p>
          <h2 id="utterance-graph-title">{t('graph.title')}</h2>
          <p>{t('graph.description')}</p>
        </div>
        <div className="graph-legend" aria-label={t('graph.legend')}>
          <span><i className="timeline-key" />{t('graph.timeline')}</span>
          <span><i className="similarity-key" />{t('graph.similarity')}</span>
        </div>
      </header>
      {graph.nodes.length === 0 ? (
        <div className="graph-empty"><span aria-hidden="true">⌁</span><p>{t('graph.empty')}</p></div>
      ) : (
        <svg className="graph-canvas" viewBox="0 0 1000 430" role="img" aria-label={t('graph.canvas')}>
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
                    aria-label={t('graph.node', { value: index + 1 })}
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
