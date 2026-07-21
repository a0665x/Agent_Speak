# UI

## Project guide

`/` is a concise Traditional Chinese project guide. It contains three primary destinations: API Explorer (`/docs`), ASR Realtime (`/asr_realtime`), and live System Status populated from `/api/v1/health` plus `/api/v1/capabilities`. The landing page uses only local assets and never asks for microphone permission, opens a WebSocket, invokes an Agent, or runs TTS.

The visual system uses graphite surfaces, restrained ice-blue/violet gradients, generated speech-core artwork, system typography, and immediate press feedback. Controls and links have visible keyboard focus, minimum 44 px targets, reduced-motion/transparency and increased-contrast fallbacks, and responsive layouts without horizontal page scrolling.

## ASR Realtime

`/asr_realtime` is the canonical React/Vite continuous transcription surface; `/realtime` redirects there for compatibility. It requires an explicit browser device check that confirms both Zone Vibe 100 `audioinput` and `audiooutput` before Start Listening is enabled. Enumeration proves browser visibility only, not physical playback. Starting creates a normal API session and sends exact 20 ms, 16 kHz mono PCM16 frames over `WS /api/v1/realtime/sessions/{session_id}`; raw audio never crosses MCP JSON-RPC and is not persisted.

The five-stage process cycle is `Listening → Voice detected → ASR partial → Endpoint → Correction`. Actual ordered Gateway events select the semantic stage. The current stage is brightest; the previous stage retains a 1.45-second visual afterglow before fading. The afterglow timer controls presentation only and never advances pipeline state.

Rolling partial hypotheses may change. Qwen may revise only the current and previous sentence; the previous row then locks and older rows never change. Endpoint candidate timing is 900 ms with a 1,800 ms hard boundary. Timeout, invalid JSON, protected-token loss, or excessive edit distance preserves raw final ASR. The current deployed VAD provider is reported from capabilities and must not be represented as Silero when `energy-vad` is active.

Each completed endpoint becomes one bounded utterance graph node. Partial ASR never creates nodes. Solid edges show chronological order; dashed edges show deterministic local text-feature cosine similarity. The graph retains at most 24 nodes for the active browser session and does not persist text vectors. SVG node translation, fixed 36 px pointer target, and inner visual scaling are separate layers, so hovering shows escaped corrected text without changing coordinates or producing pointer jitter.

Ambient Waves are a locally vendored, visually subordinate React Bits adaptation. The microphone envelope is drawn separately from real local samples. Text and icons carry every status, 44–48 px controls remain keyboard reachable, mobile layouts avoid horizontal scrolling, and reduced motion disables ambient/pulse/scale effects while preserving semantic contrast. CPU mode remains functional; model and device labels report actual capabilities.

This page stops at corrected transcription. It never invokes an Agent, TTS, Codex injection, or speaker output, and it does not reconnect or restart capture automatically.

## Codex CLI voice recorder

The dedicated `/codex` page remains a compact Traditional Chinese clipboard recorder. It is separate from `/asr_realtime` and never calls the development Agent or TTS stages. The operator remains responsible for pasting the corrected text into Codex CLI and pressing Enter; the page must not claim direct session injection.

Recording stays disabled until an explicit device check gives the browser microphone permission and confirms both a Zone Vibe 100 `audioinput` and `audiooutput`. Device checking stops its temporary permission stream immediately and does not record or play sound. A `devicechange` event invalidates the check and disables recording until the operator checks again.

The page uses separate Start and Stop buttons. Recording stops automatically at 30 seconds. The browser converts bounded audio to mono 16-bit PCM WAV, calls `/api/v1/audio/asr` followed by `/api/v1/text/correct`, displays raw and corrected text, and attempts `navigator.clipboard.writeText`. Clipboard denial keeps the text visible and exposes a manual copy control.

External Agents continue to use the host-owned interaction `listen_once → external reasoning/tools → speak`; no webpage replaces that contract.
