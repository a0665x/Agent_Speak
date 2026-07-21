import { FileLock2, PencilLine, Radio } from 'lucide-react';
import type { TranscriptRow } from '../state/reducer';
import { useI18n, type MessageKey } from '../i18n';

export function TranscriptPanel({ rows }: { rows: TranscriptRow[] }) {
  const { t } = useI18n();
  return (
    <section className="transcript-panel" aria-labelledby="transcript-title">
      <div className="section-heading">
        <p className="eyebrow">{t('transcript.eyebrow')}</p>
        <h2 id="transcript-title">{t('transcript.title')}</h2>
      </div>
      <div className="transcript-rows" aria-live="polite">
        {rows.length === 0 && <p className="empty-state">{t('transcript.empty')}</p>}
        {rows.map(row => (
          <article key={row.utteranceId} className={`transcript-row ${row.status}`} aria-label={t('transcript.rowAria', { text: row.text, status: label(row.status, t) })}>
            {row.status === 'locked' ? <FileLock2 /> : row.status === 'partial' ? <Radio /> : <PencilLine />}
            <p>{row.text}</p>
            <span>{label(row.status, t)}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

function label(status: TranscriptRow['status'], t: (key: MessageKey) => string) {
  return t(status === 'locked' ? 'transcript.locked' : status === 'partial' ? 'transcript.partial' : 'transcript.editable');
}
