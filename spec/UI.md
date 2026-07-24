# UI

## Project guide

`/` is a concise multilingual project guide. English is the default, with complete presentation catalogs for `en`, `zh-TW`, `ja`, and `ko`. Locale resolution is `query parameter → localStorage → English`; the top-right selector persists the choice and propagates it into links for API Explorer (`/docs`), ASR Realtime (`/asr_realtime`), TTS Clone Test (`/tts_clone_test`), and live System Status populated from `/api/v1/health` plus `/api/v1/capabilities`. The landing page uses only local assets and never asks for microphone permission, opens a WebSocket, invokes an Agent, or runs TTS.

The visual system uses graphite surfaces, restrained ice-blue/violet gradients, generated speech-core artwork, system typography, and immediate press feedback. Its hero message presents the product as a local voice layer that lets any Agent listen freely and naturally join a conversation. A full-viewport Canvas 2D particle field adds spatial depth while remaining near black at rest. Actual pointer movement injects energy along the interpolated path, making larger particles brighten and repel before springing back and fading over approximately four seconds; a stationary pointer does not refresh the trail. The canvas is decorative, ignores pointer events, and becomes a static low-luminance composition when reduced motion is requested. Controls and links have visible keyboard focus, minimum 44 px targets, reduced-motion/transparency and increased-contrast fallbacks, and responsive layouts without horizontal page scrolling.

## ASR Realtime

`/asr_realtime` is the canonical React/Vite continuous transcription surface; `/realtime` redirects there for compatibility. Its localized hero is titled “ASR Realtime Demo” and immediately orients the user toward model selection, processing state, and transcript data visualization. It requires an explicit browser device check that confirms both system-default `audioinput` and `audiooutput` before Start Listening is enabled, falling back to the first labeled endpoint of each kind when `default` is absent. Enumeration proves browser visibility only, not physical playback. Starting creates a normal API session and sends exact 20 ms, 16 kHz mono PCM16 frames over `WS /api/v1/realtime/sessions/{session_id}`; raw audio never crosses MCP JSON-RPC and is not persisted.

The same top-right selector localizes all presentation copy in English, Traditional Chinese, Japanese, or Korean without resetting completed transcripts, graph nodes, device state, or the realtime pipeline. It keeps the current locale in the URL and storage and passes it back to the project guide and Swagger UI.

The five-stage process cycle is `Listening → Voice detected → ASR partial → Endpoint → Correction`. Actual ordered Gateway events select the semantic stage. The current stage is brightest; the previous stage retains a 1.45-second visual afterglow before fading. The afterglow timer controls presentation only and never advances pipeline state.

Rolling partial hypotheses may change. Qwen may revise only the current and previous sentence; the previous row then locks and older rows never change. Endpoint candidate timing is 900 ms with a 1,800 ms hard boundary. Timeout, invalid JSON, protected-token loss, or excessive edit distance preserves raw final ASR. The current deployed VAD provider is reported from capabilities and must not be represented as Silero when `energy-vad` is active.

Each completed endpoint becomes one bounded utterance graph node. Partial ASR never creates nodes. Solid edges show chronological order; dashed edges show deterministic local text-feature cosine similarity. The graph retains at most 24 nodes for the active browser session and does not persist text vectors. SVG node translation, fixed 36 px pointer target, and inner visual scaling are separate layers, so hovering shows escaped corrected text without changing coordinates or producing pointer jitter.

The ASR surface reuses the portal particle engine with similarly cinematic density and the same movement-only displacement and four-second energy decay. Its active peak remains modestly dimmer than the homepage so transcript and status information stay dominant, but the dormant field no longer looks empty. The microphone envelope is drawn separately from real local samples. Text and icons carry every status, 44–48 px controls remain keyboard reachable, mobile layouts avoid horizontal scrolling, and reduced motion disables ambient/pulse/scale effects while preserving semantic contrast. CPU mode remains functional; model and device labels report actual capabilities.

The Active Models card uses immediate ASR and correction selects with no Submit button. Its lifecycle label exposes loading, warming, ready, rollback, failure, and device state. Switching while listening closes the current stream, discards its unfinished partial, activates one resident ASR provider, creates a new frozen session, and resumes only while the generic system-audio gate remains ready. Completed transcript rows and graph nodes remain visible. Live Audio renders three smooth, symmetric gradient signal ribbons from the real envelope instead of a single polygonal line; reduced motion removes pulse animation without hiding amplitude.

**Reset ASR resources** is a separate explicit lifecycle action. During an active stream it confirms first, closes capture, preserves completed transcript/graph nodes, discards only the unfinished partial, and displays `releasing → starting → warming → ready|failed`. It refreshes model/capability truth after reconnect but never resumes listening or reopens a device automatically.

This page stops at corrected transcription. It never invokes an Agent, TTS, Codex injection, or speaker output, and it does not reconnect or restart capture automatically.

## TTS Clone Test

`/tts_clone_test` is the four-language VoxCPM2 surface. It polls runtime status but does not request microphone permission on load. The explicit device check must see both a generic microphone and speaker before capture/generation controls open. CPU, wrong-mode, loading, and worker-failure states remain browsable and show operator recovery hints.

Voice Clone and TTS Play are freely switchable tabs. Voice Clone keeps at most one valid 5–30 second PCM reference in browser memory; a valid new recording replaces it, while invalid capture leaves the old valid reference intact. This is zero-shot conditioning rather than training or LoRA. TTS Play can skip cloning, preserves text after failure, converts friendly cue identifiers into best-effort natural-language delivery instructions, and separates **Generate** from **Play** so synthesis never causes autoplay.

**Reset TTS resources** remains available while the page is browsable. It confirms before stopping an active recording, generation, or playback, preserves the current text, style cues, and valid in-memory reference, then displays the bounded resource operation phases. Readiness never triggers a device check, generation, or playback; every audio action still requires its own user click.

The central 2D gradient Voice Orb reacts to real recording amplitude/VAD, deterministic validation/queue/generation phases, and real playback amplitude. Text/live regions duplicate every visual state. Completed playback settles into Complete; reduced motion removes continuous geometry movement. Reference/generated Blob URLs are revoked on replacement or page unload. Neither audio nor text is persisted by the page or Gateway.

## Codex CLI voice recorder

The dedicated `/codex` page remains a compact Traditional Chinese clipboard recorder. It is separate from `/asr_realtime` and never calls the development Agent or TTS stages. The operator remains responsible for pasting the corrected text into Codex CLI and pressing Enter; the page must not claim direct session injection.

Recording stays disabled until an explicit device check gives the browser microphone permission and confirms both a system-default `audioinput` and `audiooutput`, or the first labeled fallback endpoints. No brand name or Bluetooth label is required. Device checking stops its temporary permission stream immediately and does not record or play sound. A `devicechange` event invalidates the check and disables recording until the operator checks again.

The page uses separate Start and Stop buttons. Recording stops automatically at 30 seconds. The browser converts bounded audio to mono 16-bit PCM WAV, calls `/api/v1/audio/asr` followed by `/api/v1/text/correct`, displays raw and corrected text, and attempts `navigator.clipboard.writeText`. Clipboard denial keeps the text visible and exposes a manual copy control.

External Agents continue to use the host-owned interaction `listen_once → external reasoning/tools → speak`; no webpage replaces that contract.

## AI Avatar Motion Lab

`/ai_avatar` is an English-first, audio-free Henry animation preview. It loads
the approved v4 manifest and all 164 unique 512 × 512 RGBA PNG frames before
enabling Idle, Listening, Thinking, Speaking, Happy, or Error. It never requests
devices, captures audio, invokes ASR/Agent/TTS, or plays sound.

Every clip starts and ends on byte-identical `henry_s0`. A click changes only
the latest queued state while the current loop continues. The final shared S0
is displayed before the queued state becomes active, so switching does not cut
a gesture or require a crossfade. Playing and Queued text duplicate the visual
button state.

The fixed Canvas stage uses a dark ice-blue/violet liquid-glass presentation,
subtle local particles, semantic state buttons, Pause/Resume, Restart, and a
collapsible runtime panel. Controls stay disabled until Assets Ready, have
visible keyboard focus and at least 44 px targets, collapse to one column below
900 px, and remove continuous decorative animation for reduced motion.
