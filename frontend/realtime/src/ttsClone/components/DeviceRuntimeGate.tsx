import { Cpu, Mic, Radio, Server, Volume2, Waves } from 'lucide-react';
import type { CloneStatus } from '../types';

type GateValue = 'unchecked' | 'checking' | 'ready' | 'missing';

type GateLabels = {
  microphone: string;
  speaker: string;
  cuda: string;
  worker: string;
  model: string;
  reference: string;
  ready: string;
  waiting: string;
  missing: string;
};

export function DeviceRuntimeGate({
  microphone,
  speaker,
  status,
  hasReference,
  labels,
}: {
  microphone: GateValue;
  speaker: GateValue;
  status?: CloneStatus;
  hasReference: boolean;
  labels: GateLabels;
}) {
  const deviceState = (value: GateValue) =>
    value === 'ready' ? 'ready' : value === 'missing' ? 'missing' : 'waiting';
  const runtimeState = (ready: boolean, failed = false) =>
    ready ? 'ready' : failed ? 'missing' : 'waiting';
  const items = [
    { label: labels.microphone, state: deviceState(microphone), Icon: Mic },
    { label: labels.speaker, state: deviceState(speaker), Icon: Volume2 },
    {
      label: labels.cuda,
      state: runtimeState(status?.accelerator === 'nvidia', status?.accelerator === 'cpu'),
      Icon: Cpu,
    },
    {
      label: labels.worker,
      state: runtimeState(Boolean(status?.ready), status?.state === 'failed'),
      Icon: Server,
    },
    {
      label: labels.model,
      state: runtimeState(Boolean(status?.ready), status?.state === 'failed'),
      Icon: Waves,
    },
    {
      label: labels.reference,
      state: hasReference ? 'ready' : 'waiting',
      Icon: Radio,
    },
  ] as const;

  return (
    <section className="runtime-gate" aria-label="Runtime prerequisites">
      <div className="runtime-gate__grid">
        {items.map(({ label, state, Icon }) => (
          <div className="runtime-signal" data-state={state} key={label}>
            <span className="runtime-signal__icon"><Icon aria-hidden="true" size={16} /></span>
            <span>
              <strong>{label}</strong>
              <small>
                {state === 'ready' ? labels.ready : state === 'missing' ? labels.missing : labels.waiting}
              </small>
            </span>
            <i aria-hidden="true" />
          </div>
        ))}
      </div>
      {status?.operatorHint && (
        <code className="operator-hint">{status.operatorHint}</code>
      )}
    </section>
  );
}
