import { Headphones, Mic, ShieldCheck } from 'lucide-react';
import type { DeviceGateResult } from '../types';

export function DeviceGate({ gate }: { gate: DeviceGateResult }) {
  return (
    <section className="device-gate" aria-labelledby="device-gate-title">
      <div className="device-title">
        <span className="device-ready-dot" aria-hidden="true" />
        <div>
        <p className="eyebrow"><ShieldCheck size={16} /> DEVICE GATE</p>
        <h2 id="device-gate-title">Zone Vibe 100</h2>
        </div>
      </div>
      <div className="device-list">
        <p><Mic aria-hidden="true" /> <span>{gate.input?.label ?? '麥克風尚未確認'}</span></p>
        <p><Headphones aria-hidden="true" /> <span>{gate.output?.label ?? '音訊輸出尚未確認'}</span></p>
      </div>
    </section>
  );
}
