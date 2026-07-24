import type { AvatarState } from '../types/avatar';

export interface AvatarStateSnapshot {
  playingState: AvatarState;
  pendingState: AvatarState | null;
}

export class AvatarStateMachine {
  private playingState: AvatarState;
  private pendingState: AvatarState | null = null;

  constructor(initialState: AvatarState) {
    this.playingState = initialState;
  }

  select(state: AvatarState): boolean {
    if (state === this.playingState) {
      this.pendingState = null;
      return false;
    }
    this.pendingState = state;
    return true;
  }

  completeLoop(): boolean {
    if (this.pendingState === null) {
      return false;
    }
    this.playingState = this.pendingState;
    this.pendingState = null;
    return true;
  }

  clearPending(): void {
    this.pendingState = null;
  }

  snapshot(): AvatarStateSnapshot {
    return {
      playingState: this.playingState,
      pendingState: this.pendingState,
    };
  }
}
