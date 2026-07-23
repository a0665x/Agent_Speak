export class ClipScheduler {
  private persistentClip = "idle_loop";
  private activeClip = "idle_loop";
  setPersistentClip(id: string) { this.persistentClip = id; this.activeClip = id; }
  playOnce(id: string) { this.activeClip = id; }
  completeOnce() { this.activeClip = this.persistentClip; }
  getActiveClip() { return this.activeClip; }
}
