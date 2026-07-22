import type { ASRModelId, CorrectionModelId, ModelCatalog } from '../models';
import type { ModelPresentation } from '../modelPresentation';
import { useI18n } from '../i18n';

type Props = {
  catalog: ModelCatalog;
  asrModel: ASRModelId;
  correctionModel: CorrectionModelId;
  switching: boolean;
  presentation: ModelPresentation;
  statusText: string;
  onChange: (asrModel: ASRModelId, correctionModel: CorrectionModelId) => void;
};

export function ActiveModels({ catalog, asrModel, correctionModel, switching, presentation, statusText, onChange }: Props) {
  const { t } = useI18n();

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
      <p
        className={`model-lifecycle state-${presentation.ready ? 'ready' : presentation.lifecycle}${presentation.switching ? ' is-switching' : ''}`}
        role="status"
        aria-live="polite"
        data-ready={presentation.ready ? 'true' : 'false'}
      >
        <span className={presentation.switching ? 'model-spinner' : ''} aria-hidden="true" />
        {statusText} · {presentation.device}
      </p>
    </div>
  );
}
