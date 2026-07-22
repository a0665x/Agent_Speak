import type { ASRModelId, CorrectionModelId, ModelCatalog } from '../models';
import { useI18n } from '../i18n';

type Props = {
  catalog: ModelCatalog;
  asrModel: ASRModelId;
  correctionModel: CorrectionModelId;
  switching: boolean;
  onChange: (asrModel: ASRModelId, correctionModel: CorrectionModelId) => void;
};

export function ActiveModels({ catalog, asrModel, correctionModel, switching, onChange }: Props) {
  const { t } = useI18n();
  const stateLabels = {
    ready: t('models.state.ready'), loading: t('models.state.loading'), warming: t('models.state.warming'),
    unloading: t('models.state.unloading'), rollback: t('models.state.rollback'), failed: t('models.state.failed'),
    idle: t('models.state.idle'), unavailable: t('models.state.unavailable'),
  } as const;
  const lifecycle = switching ? t('models.switching') : stateLabels[catalog.active.state as keyof typeof stateLabels];

  return (
    <div className="model-selectors">
      <label>
        <span>{t('models.asrLabel')}</span>
        <select
          aria-label={t('models.asrLabel')}
          value={asrModel}
          disabled={switching}
          onChange={event => onChange(event.target.value as ASRModelId, correctionModel)}
        >
          {catalog.asr.map(model => (
            <option key={model.id} value={model.id} disabled={!model.ready}>{model.label}</option>
          ))}
        </select>
      </label>
      <label>
        <span>{t('models.correctionLabel')}</span>
        <select
          aria-label={t('models.correctionLabel')}
          value={correctionModel}
          disabled={switching}
          onChange={event => onChange(asrModel, event.target.value as CorrectionModelId)}
        >
          {catalog.correction.map(model => (
            <option key={model.id} value={model.id} disabled={!model.ready}>{model.label}</option>
          ))}
        </select>
      </label>
      <p className={`model-lifecycle state-${catalog.active.state}`} role="status">
        <span aria-hidden="true" />{lifecycle || catalog.active.state} · {catalog.active.device}
      </p>
    </div>
  );
}
