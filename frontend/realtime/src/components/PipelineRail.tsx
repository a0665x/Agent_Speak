import { AudioLines, CheckCheck, MessageSquareText, TimerReset } from 'lucide-react';
import { useI18n } from '../i18n';

export function PipelineRail({ state, queue, endpointMs }: { state: string; queue: number; endpointMs: number }) {
  const { t } = useI18n();
  const stages = [
    { key: 'vad', label: 'VAD', value: ['speech', 'listening'].includes(state) ? state : t('pipeline.standby'), icon: AudioLines },
    { key: 'endpoint', label: t('models.endpoint'), value: state === 'endpoint' ? `${endpointMs} ms` : t('pipeline.standby'), icon: TimerReset },
    { key: 'asr', label: t('models.queue'), value: t('pipeline.pending', { value: queue }), icon: MessageSquareText },
    { key: 'correction', label: t('models.correction'), value: state === 'correcting' ? t('pipeline.processing') : t('pipeline.standby'), icon: CheckCheck }
  ];
  return (
    <aside className="pipeline-rail" aria-label={t('pipeline.aria')}>
      {stages.map(({ key, label, value, icon: Icon }) => (
        <div className={`pipeline-stage ${state.includes(key) ? 'active' : ''}`} key={key}>
          <Icon aria-hidden="true" />
          <div><strong>{label}</strong><span>{value}</span></div>
        </div>
      ))}
    </aside>
  );
}
