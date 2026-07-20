import { FileLock2, PencilLine, Radio } from 'lucide-react';
import type { TranscriptRow } from '../state/reducer';

export function TranscriptPanel({ rows }: { rows: TranscriptRow[] }) {
  return (
    <section className="transcript-panel" aria-labelledby="transcript-title">
      <div className="section-heading">
        <p className="eyebrow">LIVE TRANSCRIPT</p>
        <h2 id="transcript-title">即時逐句文字</h2>
      </div>
      <div className="transcript-rows" aria-live="polite">
        {rows.length === 0 && <p className="empty-state">開始後，辨識文字會依序出現在這裡。</p>}
        {rows.map(row => (
          <article key={row.utteranceId} className={`transcript-row ${row.status}`} aria-label={`${row.text}，${label(row.status)}`}>
            {row.status === 'locked' ? <FileLock2 /> : row.status === 'partial' ? <Radio /> : <PencilLine />}
            <p>{row.text}</p>
            <span>{label(row.status)}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

function label(status: TranscriptRow['status']) {
  return status === 'locked' ? '已鎖定' : status === 'partial' ? '暫定辨識' : '仍可隨下一句校正';
}
