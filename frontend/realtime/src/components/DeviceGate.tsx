import { Headphones, Mic, ShieldCheck } from 'lucide-react';
import type { DeviceGateResult } from '../types';
import { useI18n } from '../i18n';

export function DeviceGate({ gate }: { gate: DeviceGateResult }) {
  const { t } = useI18n();
  return (
    <section className="device-gate" aria-labelledby="device-gate-title">
      <div className="device-title">
        <span className="device-ready-dot" aria-hidden="true" />
        <div>
        <p className="eyebrow"><ShieldCheck size={16} /> {t('device.eyebrow')}</p>
        <h2 id="device-gate-title">{t('device.title')}</h2>
        </div>
      </div>
      <div className="device-list">
        <p><Mic aria-hidden="true" /> <span>{gate.input?.label ?? t('device.inputMissing')}</span></p>
        <p><Headphones aria-hidden="true" /> <span>{gate.output?.label ?? t('device.outputMissing')}</span></p>
      </div>
    </section>
  );
}
