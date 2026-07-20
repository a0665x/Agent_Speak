# UI

The operator console is served at `/`. It uses warm neutral surfaces, one restrained green accent, system sans typography, and no external media. Main areas: status, recording hero, pipeline timeline, transcript/response, latency, provider capabilities, and speaker profiles.

Required states: connecting, ready, recording, processing, completed, empty, actionable error. Controls support keyboard focus, ARIA live updates, reduced motion, and 390px/360px layouts.

The build-free console uses only local HTML/CSS/JavaScript and system fonts. MediaRecorder capture is converted in-browser to mono 16-bit WAV before the full-turn request. Recording auto-stops at the configured MVP bound of 30 seconds. Source and converted audio above 8 MiB are rejected before upload, and both recording and file upload are disabled throughout conversion and turn processing. The WebSocket timeline replays ordered events, deduplicates sequences after bounded reconnect, and updates each stage. Upload is a visible fallback. Speaker controls create/select/rename/delete profiles and enroll/match the last WAV while repeating the non-authentication notice.

The default locale is Traditional Chinese (`zh-TW`, document language `zh-Hant-TW`). The header language control switches the full static and runtime UI to English and persists the choice under `localStorage["agent-speak-locale"]`; an unknown or absent value falls back to Traditional Chinese. Completed transcript and Agent response content are user/runtime data and must never be replaced by translated empty-state copy during a language switch.

The information architecture is beginner-first: a three-step quick start explains capture, pipeline observation, and results; the recording entry follows immediately; the six-stage timeline explains what is happening; transcript/response is the primary output; capabilities and speaker profiles are explicitly marked advanced; a VAD/ASR/TTS glossary closes the page. Every major section includes a one-sentence purpose statement.

## Codex CLI voice recorder

The dedicated `/codex` page is a compact Traditional Chinese clipboard recorder for the currently open Codex CLI conversation. It is separate from the complete `/` pipeline console and never calls the development Agent or TTS stages. The operator remains responsible for pasting the corrected text into Codex CLI and pressing Enter; the page must not claim direct session injection.

Recording stays disabled until an explicit device check gives the browser microphone permission and confirms both a Zone Vibe 100 `audioinput` and `audiooutput`. Device checking stops its temporary permission stream immediately and does not record or play sound. A `devicechange` event invalidates the check and disables recording until the operator checks again. Output enumeration means only that the browser can see the endpoint; it is not proof of physical playback.

The page uses separate Start and Stop buttons. Start is available only after the dual-device gate passes, Stop is available only while recording, and both are disabled during processing. Recording stops automatically at 30 seconds. The browser converts bounded audio to mono 16-bit PCM WAV, calls `/api/v1/audio/asr` followed by `/api/v1/text/correct`, displays raw and corrected text, and attempts `navigator.clipboard.writeText`. Clipboard denial keeps the text visible and exposes a manual copy control.
