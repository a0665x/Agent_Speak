# UI

The operator console is served at `/`. It uses warm neutral surfaces, one restrained green accent, system sans typography, and no external media. Main areas: status, recording hero, pipeline timeline, transcript/response, latency, provider capabilities, and speaker profiles.

Required states: connecting, ready, recording, processing, completed, empty, actionable error. Controls support keyboard focus, ARIA live updates, reduced motion, and 390px/360px layouts.

The build-free console uses only local HTML/CSS/JavaScript and system fonts. MediaRecorder capture is converted in-browser to mono 16-bit WAV before the full-turn request. Recording auto-stops at the configured MVP bound of 30 seconds. Source and converted audio above 8 MiB are rejected before upload, and both recording and file upload are disabled throughout conversion and turn processing. The WebSocket timeline replays ordered events, deduplicates sequences after bounded reconnect, and updates each stage. Upload is a visible fallback. Speaker controls create/select/rename/delete profiles and enroll/match the last WAV while repeating the non-authentication notice.
