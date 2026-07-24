import {
  AVATAR_STATES,
  type AvatarFrameLoader,
  type AvatarManifest,
  type AvatarState,
  type ClipDefinition,
  type ClipId,
  type FrameDefinition,
  type LoadedAvatarAssets,
  type PreloadResult,
} from '../../../../AI_Avatar/frontend/types/avatar';

const SHA256 = /^[0-9a-f]{64}$/;
const FRAME_ID = /^[a-z0-9_]+$/;

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function number(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`${label} must be a finite number`);
  }
  return value;
}

function projectAssetPath(value: unknown, frameId: string): string {
  if (
    typeof value !== 'string'
    || !value.startsWith('assets/clips/')
    || value.startsWith('/')
    || value.includes('\\')
    || value.split('/').includes('..')
    || !value.endsWith('.png')
  ) {
    throw new Error(
      `frame ${frameId} src must be a project-relative asset path`,
    );
  }
  return value;
}

function parseFrames(value: unknown): Record<string, FrameDefinition> {
  const payload = record(value, 'frames');
  const frames: Record<string, FrameDefinition> = {};
  for (const [frameId, raw] of Object.entries(payload)) {
    if (!FRAME_ID.test(frameId)) {
      throw new Error(`invalid frame id: ${frameId}`);
    }
    const frame = record(raw, `frame ${frameId}`);
    const sha256 = frame.sha256;
    if (typeof sha256 !== 'string' || !SHA256.test(sha256)) {
      throw new Error(`frame ${frameId} sha256 is invalid`);
    }
    frames[frameId] = {
      src: projectAssetPath(frame.src, frameId),
      sha256,
    };
  }
  if (Object.keys(frames).length === 0) {
    throw new Error('manifest must define at least one frame');
  }
  return frames;
}

function parseClip(
  value: unknown,
  state: AvatarState,
  transitionFrameId: string,
  frames: Readonly<Record<string, FrameDefinition>>,
): ClipDefinition {
  const clip = record(value, `${state} clip`);
  if (clip.state !== state) {
    throw new Error(`${state} clip state does not match its id`);
  }
  const fps = number(clip.fps, `${state} clip fps`);
  if (fps <= 0 || fps > 60) {
    throw new Error(`${state} clip fps must be between 1 and 60`);
  }
  if (clip.loop !== true || clip.quality_status !== 'approved') {
    throw new Error(`${state} clip must be an approved loop`);
  }
  if (!Array.isArray(clip.frames) || clip.frames.length < 3) {
    throw new Error(`${state} clip must contain at least three frames`);
  }
  const frameIds = clip.frames.map((frameId) => {
    if (typeof frameId !== 'string' || !(frameId in frames)) {
      throw new Error(`${state} clip references an unknown frame`);
    }
    return frameId;
  });
  if (
    frameIds[0] !== transitionFrameId
    || frameIds[frameIds.length - 1] !== transitionFrameId
  ) {
    throw new Error(`${state} clip must use the shared transition frame`);
  }
  return {
    state,
    fps,
    loop: true,
    quality_status: 'approved',
    frames: Object.freeze(frameIds),
  };
}

export function parseManifest(value: unknown): AvatarManifest {
  const payload = record(value, 'avatar manifest');
  if (payload.version !== '4.0') {
    throw new Error('avatar manifest version must be 4.0');
  }
  if (typeof payload.character !== 'string' || !payload.character.trim()) {
    throw new Error('avatar manifest character is required');
  }
  const viewportPayload = record(payload.viewport, 'viewport');
  const viewport = {
    width: number(viewportPayload.width, 'viewport width'),
    height: number(viewportPayload.height, 'viewport height'),
    anchor_x: number(viewportPayload.anchor_x, 'viewport anchor_x'),
    anchor_y: number(viewportPayload.anchor_y, 'viewport anchor_y'),
  };
  if (
    viewport.width <= 0
    || viewport.height <= 0
    || viewport.anchor_x < 0
    || viewport.anchor_x > 1
    || viewport.anchor_y < 0
    || viewport.anchor_y > 1
  ) {
    throw new Error('avatar viewport dimensions or anchor are invalid');
  }
  const transitionFrameId = payload.transition_frame_id;
  if (
    typeof transitionFrameId !== 'string'
    || !FRAME_ID.test(transitionFrameId)
  ) {
    throw new Error('shared transition frame id is invalid');
  }
  const frames = parseFrames(payload.frames);
  if (!(transitionFrameId in frames)) {
    throw new Error('shared transition frame is missing');
  }
  const clipsPayload = record(payload.clips, 'clips');
  const expectedClipIds = AVATAR_STATES.map((state) => `${state}_loop`);
  const actualClipIds = Object.keys(clipsPayload).sort();
  if (
    actualClipIds.length !== expectedClipIds.length
    || expectedClipIds.some((clipId) => !actualClipIds.includes(clipId))
  ) {
    throw new Error('manifest must define exactly the six avatar state clips');
  }
  const clips = {} as Record<ClipId, ClipDefinition>;
  for (const state of AVATAR_STATES) {
    const clipId = `${state}_loop` as ClipId;
    clips[clipId] = parseClip(
      clipsPayload[clipId],
      state,
      transitionFrameId,
      frames,
    );
  }
  return {
    version: '4.0',
    character: payload.character,
    viewport,
    transition_frame_id: transitionFrameId,
    frames: Object.freeze(frames),
    clips: Object.freeze(clips),
  };
}

function resolveSource(source: string, basePath: string): string {
  const base = basePath.endsWith('/') ? basePath : `${basePath}/`;
  return `${base}${source}`;
}

const decodeImage: AvatarFrameLoader = async (source) => {
  const image = new Image();
  image.src = source;
  await image.decode();
  return image;
};

export async function preloadManifest(
  manifest: AvatarManifest,
  load: AvatarFrameLoader = decodeImage,
  basePath = '/ai_avatar/',
): Promise<PreloadResult> {
  const uniqueSources = new Map<string, string>();
  for (const [frameId, frame] of Object.entries(manifest.frames)) {
    if (!uniqueSources.has(frame.src)) {
      uniqueSources.set(frame.src, frameId);
    }
  }
  const images = new Map<string, HTMLImageElement>();
  await Promise.all(
    [...uniqueSources.entries()].map(async ([source, frameId]) => {
      const resolved = resolveSource(source, basePath);
      try {
        const image = await load(resolved, frameId);
        if (image) {
          images.set(frameId, image);
        }
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        throw new Error(`failed to preload ${frameId}: ${detail}`);
      }
    }),
  );
  return {
    ready: true,
    loaded: uniqueSources.size,
    images,
  };
}

export async function loadManifest(
  fetcher: typeof fetch = fetch,
): Promise<LoadedAvatarAssets> {
  const response = await fetcher('/ai_avatar/manifest.json');
  if (!response.ok) {
    throw new Error(`avatar manifest request failed: ${response.status}`);
  }
  const manifest = parseManifest(await response.json());
  const preload = await preloadManifest(manifest);
  return { manifest, preload };
}
