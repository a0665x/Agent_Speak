# Codex CLI Voice Recorder Design

Date: 2026-07-20

## Goal

Add a small, independent `/codex` browser page that lets the operator record with a Logitech Zone Vibe 100 headset, transcribe and correct the utterance through the existing Agent Speak API, and move the corrected text into the currently open Codex CLI conversation through the system clipboard.

The operator remains responsible for pasting the copied text into Codex CLI and pressing Enter. The page must not claim that it has injected or submitted a turn to the Codex session.

## Chosen approach

Serve a dedicated `/codex` page with its own local JavaScript and CSS assets. This page is intentionally separate from the full operator console so the recording controls remain immediately visible and are not confused with the existing six-stage development pipeline.

The page uses browser media APIs for headset discovery and capture because the browser, not the Gateway container, owns the host Bluetooth audio endpoints. It calls only the existing `/api/v1/audio/asr` and `/api/v1/text/correct` endpoints. It does not call the Gateway development Agent or TTS provider.

## Alternatives considered

1. Add the controls to the existing `/` console. This reuses the current page but mixes a Codex clipboard workflow with the complete Gateway turn workflow and makes the quick controls harder to find.
2. Inject text directly into the active Codex CLI session. MCP tools are initiated by Codex during a turn and do not push a new user turn into an idle TUI. A supported programmatic turn flow would require a Codex app-server client to own or resume the conversation, which is outside this small feature.

## Interface

The `/codex` page contains:

- Gateway connection status.
- A `Check Zone Vibe 100 devices` action.
- Separate `Start recording` and `Stop recording` buttons.
- The selected microphone and audio-output device labels.
- Recording state and a `00:00 / 00:30` timer.
- Raw ASR transcript.
- Corrected text.
- Clipboard result and a manual `Copy text` fallback action.
- Actionable inline errors and a device recheck path.

The default language is Traditional Chinese, consistent with the existing console. Controls have visible focus states, at least 44 px touch targets, semantic disabled states, and live status announcements. The layout must work without horizontal scrolling at 360 px.

## State model

On page load, both recording buttons are disabled.

1. `unchecked`: device check is available; start and stop are disabled.
2. `checking`: the page requests microphone permission from a user gesture, then enumerates audio inputs and outputs; all recording controls remain disabled.
3. `ready`: both an audio input and audio output whose normalized label contains `zone vibe 100` are visible. Start is enabled and stop is disabled.
4. `recording`: start is disabled, stop is enabled, and the timer advances. Recording automatically stops at 30 seconds.
5. `processing`: both controls are disabled while the audio is converted, transcribed, and corrected.
6. `completed`: corrected text is displayed and an automatic clipboard write is attempted. Start is enabled again if the checked devices remain available.
7. `error`: the page shows the specific failure and a recovery action. Recording remains disabled when the device prerequisite is no longer satisfied.

`devicechange` invalidates the previous check and returns the page to a disabled state until both headset endpoints are confirmed again.

## Device and consent contract

The device check starts only after the operator presses the check action. It may request microphone permission so browser device labels become available. Any temporary permission stream opened for enumeration is stopped immediately after the check.

The page must find both a Zone Vibe 100 `audioinput` and `audiooutput`. Finding only a default device is not sufficient. The matched input device ID is used when recording begins.

Output discovery proves only that the browser can see an endpoint. The page does not play a test sound and must not claim physical playback succeeded. A future playback test would require a separate explicit user action and consent.

Every recording begins with an explicit press of `Start recording`. Loading the page or checking devices never starts recording.

## Data flow

1. The operator checks the Zone Vibe 100 input and output endpoints.
2. The operator starts and stops a bounded browser recording.
3. Browser audio is decoded and converted locally to mono 16-bit PCM WAV.
4. The page rejects source or converted audio over 8 MiB.
5. The page posts the WAV to `POST /api/v1/audio/asr`.
6. The page posts the returned transcript to `POST /api/v1/text/correct`.
7. The page displays both transcript and corrected text.
8. The page calls `navigator.clipboard.writeText` with non-empty corrected text.
9. If automatic clipboard access fails, the corrected text remains visible and a manual copy action is enabled.
10. The operator pastes the text into the current Codex CLI composer and presses Enter.

No new `/api/v1` endpoint or response shape is introduced.

## Failure handling

- Permission denial identifies the denied browser permission and offers a recheck.
- Missing headset input and missing headset output are reported separately.
- Unsupported browser recording or device APIs produce an actionable compatibility error.
- Empty audio, no speech, oversize audio, ASR failure, and correction failure retain the last useful state and never copy an empty value.
- Conversion and network failures return the page to a retryable state.
- Clipboard denial exposes the manual copy action instead of reporting completion as copied.
- Device removal disables recording immediately through `devicechange` handling.

## Privacy and safety

- The page is served locally and uses the existing loopback Gateway deployment.
- It does not read Codex session files, credentials, logs, or private Agent state.
- It does not store recordings in browser persistence or add recordings to Git.
- It does not start unbounded listening, perform physical playback, or treat output enumeration as playback proof.
- Corrected text enters Codex only after the operator pastes and submits it.

## Verification

Automated tests must be written first and observed failing before implementation. They cover:

- `/codex` and its local assets are served.
- The page contains separate start and stop buttons with the required initial disabled states.
- Zone Vibe 100 input and output are both required before start becomes available.
- Permission denial, missing input, missing output, device removal, and unsupported APIs keep recording gated.
- Start/stop state transitions, the 30-second automatic stop, and 8 MiB bounds.
- WAV conversion followed by ASR and correction requests using the unchanged API paths.
- Raw and corrected text rendering without `innerHTML`.
- Automatic clipboard success and the manual-copy fallback.
- JavaScript syntax and the full existing regression suite.

Manual acceptance requires the operator to open `/codex`, press the device check, verify both displayed Zone Vibe 100 labels, explicitly start and stop a real recording, confirm transcript and corrected text, and paste the copied result into the current Codex CLI session. No microphone or speaker action is performed without the operator's explicit button press.
