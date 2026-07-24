export const AVATAR_STATES = [
  'idle',
  'listening',
  'thinking',
  'speaking',
  'happy',
  'error',
] as const;

export type AvatarState = (typeof AVATAR_STATES)[number];
export type ClipId = `${AvatarState}_loop`;

export interface AvatarViewport {
  width: number;
  height: number;
  anchor_x: number;
  anchor_y: number;
}

export interface FrameDefinition {
  src: string;
  sha256: string;
}

export interface ClipDefinition {
  state: AvatarState;
  fps: number;
  loop: true;
  quality_status: 'approved';
  frames: readonly string[];
}

export interface AvatarManifest {
  version: '4.0';
  character: string;
  viewport: AvatarViewport;
  transition_frame_id: string;
  frames: Readonly<Record<string, FrameDefinition>>;
  clips: Readonly<Record<ClipId, ClipDefinition>>;
}

export type AvatarFrameLoader = (
  source: string,
  frameId: string,
) => Promise<HTMLImageElement | void>;

export interface PreloadResult {
  ready: true;
  loaded: number;
  images: ReadonlyMap<string, HTMLImageElement>;
}

export interface LoadedAvatarAssets {
  manifest: AvatarManifest;
  preload: PreloadResult;
}

export interface AvatarEvent {
  type: string;
  payload: Record<string, unknown>;
}
