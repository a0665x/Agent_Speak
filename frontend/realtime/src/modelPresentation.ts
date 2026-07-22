import type { ASRModelId, CorrectionModelId, ModelCatalog } from './models';

export type ModelLifecycle = 'ready' | 'loading' | 'warming' | 'unloading' | 'rollback' | 'failed' | 'idle' | 'unavailable';

export type ModelPresentation = {
  asrModel: ASRModelId;
  correctionModel: CorrectionModelId;
  device: string;
  lifecycle: ModelLifecycle;
  switching: boolean;
  ready: boolean;
};

const lifecycleStates = new Set<ModelLifecycle>([
  'ready', 'loading', 'warming', 'unloading', 'rollback', 'failed', 'idle', 'unavailable',
]);
const transitionalStates = new Set<ModelLifecycle>(['loading', 'warming', 'unloading', 'rollback', 'idle']);

export function deriveModelPresentation(
  catalog: ModelCatalog,
  selectedAsr: ASRModelId,
  selectedCorrection: CorrectionModelId,
  switchingRequested: boolean,
): ModelPresentation {
  const lifecycle = lifecycleStates.has(catalog.active.state as ModelLifecycle)
    ? catalog.active.state as ModelLifecycle
    : 'unavailable';
  const runtimeMatches = catalog.active.asr_model === selectedAsr
    && catalog.active.correction_model === selectedCorrection
    && catalog.active.requested_asr_model === null;
  const ready = !switchingRequested && lifecycle === 'ready' && runtimeMatches;
  const canStillReachTarget = lifecycle !== 'failed' && lifecycle !== 'unavailable';
  const targetPending = canStillReachTarget && (
    catalog.active.requested_asr_model !== null || catalog.active.asr_model !== selectedAsr
  );

  return {
    asrModel: selectedAsr,
    correctionModel: selectedCorrection,
    device: catalog.active.device,
    lifecycle,
    switching: !ready && (switchingRequested || transitionalStates.has(lifecycle) || targetPending),
    ready,
  };
}
