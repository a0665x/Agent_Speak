import { EventBus, type AvatarEvents } from '../events/EventBus';
import type {
  AvatarManifest,
  AvatarState,
  ClipId,
} from '../types/avatar';
import { AvatarStateMachine } from './AvatarStateMachine';
import { StateTransitionController } from './StateTransitionController';

export interface ClipSchedulerSnapshot {
  playingState: AvatarState;
  pendingState: AvatarState | null;
  clipId: ClipId;
  frameId: string;
  frameIndex: number;
  paused: boolean;
}

export class ClipScheduler {
  readonly events = new EventBus<AvatarEvents>();
  private readonly machine: AvatarStateMachine;
  private readonly transitions: StateTransitionController;
  private frameIndex = 0;
  private paused = false;
  private lastAdvanceAt: number | null = null;

  constructor(
    private readonly manifest: AvatarManifest,
    initialState: AvatarState = 'idle',
  ) {
    this.machine = new AvatarStateMachine(initialState);
    this.transitions = new StateTransitionController(this.machine, this.events);
  }

  select(state: AvatarState): boolean {
    return this.transitions.select(state);
  }

  setStateAvailable(state: AvatarState, available: boolean): void {
    this.transitions.setAvailable(state, available);
  }

  pause(): void {
    this.paused = true;
  }

  resume(): void {
    this.paused = false;
    this.lastAdvanceAt = null;
  }

  restart(): void {
    this.frameIndex = 0;
    this.lastAdvanceAt = null;
    this.machine.clearPending();
  }

  step(): string {
    if (this.paused) {
      return this.snapshot().frameId;
    }
    const clip = this.activeClip();
    this.frameIndex += 1;
    if (this.frameIndex >= clip.frames.length - 1) {
      const boundary = clip.frames[clip.frames.length - 1];
      this.transitions.onLoopBoundary();
      this.frameIndex = 0;
      return boundary;
    }
    return clip.frames[this.frameIndex];
  }

  advance(timestamp: number): string {
    if (this.paused) {
      return this.snapshot().frameId;
    }
    if (this.lastAdvanceAt === null) {
      this.lastAdvanceAt = timestamp;
      return this.snapshot().frameId;
    }
    const interval = 1000 / this.activeClip().fps;
    if (timestamp - this.lastAdvanceAt < interval) {
      return this.snapshot().frameId;
    }
    this.lastAdvanceAt = timestamp;
    return this.step();
  }

  advanceToFrame(
    frameId: string,
    options: { loopComplete?: boolean } = {},
  ): void {
    const clip = this.activeClip();
    const index = options.loopComplete
      ? clip.frames.length - 1
      : clip.frames.indexOf(frameId);
    if (index < 0 || clip.frames[index] !== frameId) {
      throw new Error(`frame ${frameId} is not part of the active clip`);
    }
    if (
      options.loopComplete
      && frameId !== this.manifest.transition_frame_id
    ) {
      throw new Error('loop completion must occur on the shared S0 frame');
    }
    if (options.loopComplete) {
      this.transitions.onLoopBoundary();
      this.frameIndex = 0;
    } else {
      this.frameIndex = index;
    }
  }

  snapshot(): ClipSchedulerSnapshot {
    const state = this.machine.snapshot();
    const clipId = `${state.playingState}_loop` as ClipId;
    const clip = this.manifest.clips[clipId];
    return {
      ...state,
      clipId,
      frameId: clip.frames[this.frameIndex],
      frameIndex: this.frameIndex,
      paused: this.paused,
    };
  }

  private activeClip() {
    return this.manifest.clips[this.snapshot().clipId];
  }
}
