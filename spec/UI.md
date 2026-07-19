# UI

The operator console is served at `/`. It uses warm neutral surfaces, one restrained green accent, system sans typography, and no external media. Main areas: status, recording hero, pipeline timeline, transcript/response, latency, provider capabilities, and speaker profiles.

Required states: connecting, ready, recording, processing, completed, empty, actionable error. Controls support keyboard focus, ARIA live updates, reduced motion, and 390px/360px layouts.

The build-free console uses only local HTML/CSS/JavaScript and system fonts. MediaRecorder capture is converted in-browser to mono 16-bit WAV before the full-turn request. Recording auto-stops at the configured MVP bound of 30 seconds. Source and converted audio above 8 MiB are rejected before upload, and both recording and file upload are disabled throughout conversion and turn processing. The WebSocket timeline replays ordered events, deduplicates sequences after bounded reconnect, and updates each stage. Upload is a visible fallback. Speaker controls create/select/rename/delete profiles and enroll/match the last WAV while repeating the non-authentication notice.

The default locale is Traditional Chinese (`zh-TW`, document language `zh-Hant-TW`). The header language control switches the full static and runtime UI to English and persists the choice under `localStorage["agent-speak-locale"]`; an unknown or absent value falls back to Traditional Chinese. Completed transcript and Agent response content are user/runtime data and must never be replaced by translated empty-state copy during a language switch.

The information architecture is beginner-first: a three-step quick start explains capture, pipeline observation, and results; the recording entry follows immediately; the six-stage timeline explains what is happening; transcript/response is the primary output; capabilities and speaker profiles are explicitly marked advanced; a VAD/ASR/TTS glossary closes the page. Every major section includes a one-sentence purpose statement.
