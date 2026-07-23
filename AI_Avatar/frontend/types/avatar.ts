export type AvatarState = "OFFLINE" | "BOOTING" | "IDLE" | "LISTENING" | "RECOGNIZING" | "THINKING" | "SPEAKING" | "SPEAKING_HAPPY" | "SLEEPING" | "SUCCESS" | "CONFUSED" | "ERROR";

export interface AnimationClip {
  sheet: string; row: number; frame_count: number; fps: number; loop: boolean; duration_ms: number; frames_dir: string; gif_path: string; webp_path: string; return_policy?: string | null;
}

export interface AvatarEvent { type: string; payload: Record<string, unknown>; }
