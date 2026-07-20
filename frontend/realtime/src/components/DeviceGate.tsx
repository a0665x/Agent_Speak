import { Headphones, Mic, ShieldCheck } from 'lucide-react';
import type { DeviceGateResult } from '../types';

export function DeviceGate({ gate }: { gate: DeviceGateResult }) {
  return (
    <section className="device-gate" aria-labelledby="device-gate-title">
      <div>
        <p className="eyebrow"><ShieldCheck size={16} /> DEVICE GATE</p>
        <h2 id="device-gate-title">Zone Vibe 100</h2>
      </div>
      <p><Mic aria-hidden="true" /> {gate.input?.label ?? '麥克風尚未確認'}</p>
      <p><Headphones aria-hidden="true" /> {gate.output?.label ?? '音訊輸出尚未確認'}</p>
    </section>
  );
}
