import { AudioLines, CheckCheck, MessageSquareText, TimerReset } from 'lucide-react';

export function PipelineRail({ state, queue, endpointMs }: { state: string; queue: number; endpointMs: number }) {
  const stages = [
    { key: 'vad', label: 'VAD', value: ['speech', 'listening'].includes(state) ? state : 'standby', icon: AudioLines },
    { key: 'endpoint', label: 'Endpoint', value: state === 'endpoint' ? `${endpointMs} ms` : 'standby', icon: TimerReset },
    { key: 'asr', label: 'ASR Queue', value: `${queue} pending`, icon: MessageSquareText },
    { key: 'correction', label: 'Correction', value: state === 'correcting' ? 'processing' : 'standby', icon: CheckCheck }
  ];
  return (
    <aside className="pipeline-rail" aria-label="Realtime pipeline 狀態">
      {stages.map(({ key, label, value, icon: Icon }) => (
        <div className={`pipeline-stage ${state.includes(key) ? 'active' : ''}`} key={key}>
          <Icon aria-hidden="true" />
          <div><strong>{label}</strong><span>{value}</span></div>
        </div>
      ))}
    </aside>
  );
}
