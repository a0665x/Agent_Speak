export type ASRModelId = 'qwen3-asr-1.7b' | 'breeze-asr-25' | 'faster-whisper-small';
export type CorrectionModelId = 'qwen2.5-correction' | 'disabled';

export type ModelOption<T extends string> = {
  id: T;
  label: string;
  description: string;
  ready: boolean;
};

export type ModelCatalog = {
  asr: ModelOption<ASRModelId>[];
  correction: ModelOption<CorrectionModelId>[];
  active: {
    asr_model: ASRModelId | null;
    correction_model: CorrectionModelId;
    requested_asr_model: ASRModelId | null;
    state: string;
    leased_by: string | null;
    device: string;
    error_code: string | null;
  };
};

export async function fetchModelCatalog(): Promise<ModelCatalog> {
  const response = await fetch('/api/v1/models');
  if (!response.ok) throw new Error('Unable to load model catalog');
  return response.json() as Promise<ModelCatalog>;
}

export async function activateModels(
  asrModel: ASRModelId,
  correctionModel: CorrectionModelId,
): Promise<ModelCatalog> {
  const response = await fetch('/api/v1/models/active', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asr_model: asrModel, correction_model: correctionModel }),
  });
  if (!response.ok) throw new Error('Unable to activate selected models');
  return response.json() as Promise<ModelCatalog>;
}
