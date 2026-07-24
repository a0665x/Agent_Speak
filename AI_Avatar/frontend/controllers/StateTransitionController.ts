import { EventBus, type AvatarEvents } from '../events/EventBus';
import type { AvatarState } from '../types/avatar';
import { AvatarStateMachine } from './AvatarStateMachine';

export class StateTransitionController {
  private readonly unavailable = new Set<AvatarState>();

  constructor(
    private readonly machine: AvatarStateMachine,
    private readonly events: EventBus<AvatarEvents>,
  ) {}

  select(state: AvatarState): boolean {
    if (this.unavailable.has(state) || !this.machine.select(state)) {
      return false;
    }
    this.events.emit('state.selected', { state });
    return true;
  }

  onLoopBoundary(): boolean {
    const completedState = this.machine.snapshot().playingState;
    this.events.emit('loop.completed', { state: completedState });
    return this.machine.completeLoop();
  }

  setAvailable(state: AvatarState, available: boolean): void {
    if (available) {
      this.unavailable.delete(state);
    } else {
      this.unavailable.add(state);
    }
  }
}
