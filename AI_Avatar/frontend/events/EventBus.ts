import type { AvatarState } from '../types/avatar';

export interface AvatarEvents {
  'state.selected': { state: AvatarState };
  'loop.completed': { state: AvatarState };
  'renderer.failed': { error: Error };
}

type Listener<Payload> = (payload: Payload) => void;

export class EventBus<Events extends object = AvatarEvents> {
  private readonly listeners = new Map<keyof Events, Set<Listener<never>>>();

  on<EventName extends keyof Events>(
    event: EventName,
    listener: Listener<Events[EventName]>,
  ): () => void {
    const listeners = this.listeners.get(event) ?? new Set();
    listeners.add(listener as Listener<never>);
    this.listeners.set(event, listeners);
    return () => this.off(event, listener);
  }

  off<EventName extends keyof Events>(
    event: EventName,
    listener: Listener<Events[EventName]>,
  ): void {
    this.listeners.get(event)?.delete(listener as Listener<never>);
  }

  emit<EventName extends keyof Events>(
    event: EventName,
    payload: Events[EventName],
  ): void {
    for (const listener of this.listeners.get(event) ?? []) {
      (listener as Listener<Events[EventName]>)(payload);
    }
  }

  clear(): void {
    this.listeners.clear();
  }
}
