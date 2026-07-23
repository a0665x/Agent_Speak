export type ReferenceQuality =
  | 'good'
  | 'too_quiet'
  | 'too_little_voice'
  | 'too_short'
  | 'too_long';

export type CloneRuntimeState = 'stopped' | 'starting' | 'loading' | 'ready' | 'failed';

export type CloneStudioState =
  | 'unavailable'
  | 'idle'
  | 'recording'
  | 'validating'
  | 'queued'
  | 'generating'
  | 'audio-ready'
  | 'playing'
  | 'complete'
  | 'error';

export type CloneStatus = {
  gpuMode: 'asr' | 'tts';
  accelerator: 'cpu' | 'nvidia';
  resourcePolicy?: 'auto' | 'exclusive' | 'concurrent' | 'multi_gpu';
  state: CloneRuntimeState;
  model: 'voxcpm2';
  device: string;
  ready: boolean;
  errorCode?: string;
  operatorHint?: string;
};

export type ReferenceAssessment = {
  durationSeconds: number;
  rms: number;
  peak: number;
  voicedRatio: number;
  quality: ReferenceQuality;
};

export type StyleCue =
  | 'light_laugh'
  | 'snicker'
  | 'sigh'
  | 'cough'
  | 'warm'
  | 'cheerful'
  | 'soft'
  | 'faster';

export type SynthesisRequest = {
  text: string;
  styleCues: StyleCue[];
  useClone: boolean;
  reference?: Blob;
};
