# Agent Speak Project Portal and ASR Realtime Experience

Date: 2026-07-21  
Status: Approved design  
Primary route: `http://127.0.0.1:8765/asr_realtime`

## Objective

Replace the legacy operator-console homepage with a concise project guide and evolve the existing realtime React application into the approved device-gated, continuous-listening experience. The UI must be driven by the existing Gateway WebSocket events, show the active speech-processing stage with a decaying afterglow, and visualize corrected utterances as an interactive text-relationship graph.

This release remains an ASR demonstration. It does not inject text into Codex, invoke an Agent, run TTS, or play sound.

## Approved product decisions

- `/` becomes a project landing page with three primary destinations: API Explorer, ASR Realtime, and live System Status.
- `/asr_realtime` becomes the canonical React application route.
- `/realtime` and its old worklet route redirect to the canonical route so existing bookmarks do not break.
- The landing page uses Apple-inspired hierarchy, restrained translucent materials, ice-blue/violet gradients, generated speech-core artwork, and immediate press feedback.
- The realtime page uses an explicit **Check devices** gate. The primary **Start Listening** button is disabled until a matching Zone Vibe 100 input and output are visible.
- Microphone capture starts only after the operator presses **Start Listening** and stops immediately on explicit stop, device invalidation, track end, or transport failure.
- The visible processing cycle is `Listening → Voice detected → ASR partial → Endpoint → Correction`.
- Stage illumination is event-driven. The current stage is brightest; the previous stage keeps a short, interruptible afterglow and then fades rather than dropping instantly.
- Each corrected endpoint becomes one utterance graph node. Partial hypotheses update the transcript but never create graph nodes.
- The latest graph node is visually dominant. Historical nodes fade by recency and regain restrained emphasis on hover without moving.
- Hovering a node shows the full corrected text. Node hit targets are fixed and independent from visual scaling to prevent pointer jitter.

## Existing architecture reused

The implementation reuses the current realtime data path without inventing a second pipeline:

```text
Zone Vibe 100 microphone
  → Browser AudioWorklet (PCM16, 16 kHz mono)
  → WS /api/v1/realtime/sessions/{session_id}
  → Gateway energy VAD and adaptive endpoint detection
  → bounded ASR worker queue
  → Faster-Whisper small (CUDA FP16 on the current NVIDIA runtime)
  → Qwen2.5-1.5B-Instruct-Q4_K_M correction via llama.cpp
  → ordered realtime events
  → React transcript, process cycle, and utterance graph
```

The current deployed VAD provider is reported truthfully as `energy-vad`; the page must not claim Silero is active. Provider and device names come from `/api/v1/capabilities` rather than hard-coded success claims.

## Routes and static assets

### `/`

The FastAPI root continues to serve local static HTML, CSS, and JavaScript, but the content becomes a project guide:

- a product hero with the generated speech-core image and short Chinese-first copy;
- an API Explorer card linking to `/docs`;
- an ASR Realtime card linking to `/asr_realtime`;
- a System Status card populated from `/api/v1/health` and `/api/v1/capabilities`;
- a compact visual explanation of `VAD → endpoint → ASR → correction`.

The landing page never asks for microphone permission.

### `/asr_realtime`

Vite uses `/asr_realtime/` as its base and builds into `web/asr_realtime`. FastAPI mounts its hashed assets under `/asr_realtime/assets`, serves the SPA index at `/asr_realtime` and `/asr_realtime/`, and serves the AudioWorklet from `/asr_realtime/pcm-capture.worklet.js` with a JavaScript content type.

### Compatibility

- `GET /realtime` redirects to `/asr_realtime`.
- `GET /realtime/` redirects to `/asr_realtime/`.
- `GET /realtime/pcm-capture.worklet.js` redirects to the canonical worklet URL.
- Public `/api/v1`, `/docs`, `/codex`, and MCP contracts remain intact.

## Realtime interaction model

### Device gate

1. The operator presses **Check devices**.
2. The browser requests microphone permission only for enumeration.
3. The temporary permission stream is stopped.
4. A matching Zone Vibe 100 `audioinput` and `audiooutput` must both exist.
5. The selected device labels are shown and **Start Listening** becomes available.
6. `devicechange`, track end, or missing selected hardware invalidates readiness and stops an active stream.

Output enumeration confirms browser visibility only; it does not play a test sound.

### Event-to-stage mapping

| Realtime event | Visible stage | Notes |
| --- | --- | --- |
| `stream.started`, `utterance.completed` | Listening | Waiting for the next utterance |
| `vad.speech_started` | Voice detected | Live envelope remains driven by captured samples |
| partial `asr.queued`, `asr.processing`, `asr.partial` | ASR partial | Rolling text remains revisable |
| `endpoint.candidate`, `endpoint.extended` | Endpoint | Shows 900 ms candidate and 1,800 ms hard boundary |
| final `asr.queued`, `asr.final`, `correction.processing` | Correction | Final ASR is preserved if correction fails |
| `transcript.revised` | Correction | Apply corrected current/previous text |
| `pipeline.warning`, `pipeline.error` | Warning/error | Do not imply successful progress |

The reducer owns the semantic stage. Components render reducer state and do not advance on timers. CSS controls only the transition between event-confirmed states.

### Stage afterglow

Each stage has `idle`, `trail`, and `active` presentation states:

- `active`: full opacity, brightest halo, clear text and icon;
- `trail`: reduced halo that fades over approximately 1.2–1.5 seconds;
- `idle`: low-contrast but readable.

Rapid event changes interrupt transitions from the current computed style. Reduced-motion mode removes scaling and pulsing while retaining the active/trail/idle contrast.

## Utterance text graph

### Node lifecycle

- Node identity is `utterance_id`.
- A node is admitted only after `utterance.completed` when a final or revised text row exists.
- If a late `transcript.revised` updates the newest revisable utterance, the existing node text and vector update in place.
- The browser retains a bounded graph for the active realtime session only; default maximum is 24 nodes.
- Starting a new realtime session clears the graph. No vectors or transcript graph data are persisted.

### Local text vector

This release must not add another model download or overload the correction worker. It computes a deterministic, local feature embedding from the corrected text in the browser:

1. normalize Unicode and case;
2. tokenize Mandarin characters, Latin words, numbers, and adjacent bi-grams;
3. hash features into a fixed-size signed vector;
4. L2-normalize the vector;
5. use cosine similarity for optional semantic edges.

This is labeled **local text similarity** in diagnostics so it is not represented as a neural embedding model. The graph component accepts an embedding provider interface so a future dedicated multilingual embedding service can replace the local provider without changing the visual component.

### Edges and layout

- A solid edge connects consecutive completed utterances.
- A dashed semantic edge connects a new node to up to two older nodes above a configurable cosine threshold.
- A deterministic bounded force-like layout derives stable coordinates from node identity, chronological anchors, and similarity attraction.
- Existing coordinates remain stable when a new node arrives; older nodes may ease a few pixels but never jump across the graph.
- The newest node has a bright core and halo. Previous nodes fade by recency with a minimum readable opacity.

### Pointer behavior

Each SVG node has three nested layers:

```text
position group (translation only)
  ├─ fixed transparent hit circle
  └─ visual group (small hover scale only)
```

The hit circle remains fixed while the visual group scales. The visual group does not receive pointer events. This prevents the SVG translation from being overwritten and avoids enter/leave oscillation near node boundaries. The tooltip shows escaped text through React text rendering, never raw HTML.

## Visual and accessibility system

- Chinese is primary; concise English technical labels may appear alongside it.
- System typography uses the platform stack and avoids external font requests.
- Background layers use oversized gradient words and low-contrast ambient forms without obscuring controls.
- Generated raster artwork is stored as a tracked web asset with useful alternative text and fixed aspect ratio.
- Buttons provide pointer-down feedback immediately; route navigation is not delayed for animation.
- Interactive targets are at least 44×44 px, keyboard focus is visible, and status changes have an `aria-live` text equivalent.
- `prefers-reduced-motion`, `prefers-reduced-transparency`, and increased-contrast fallbacks preserve usability.
- Mobile layout has no horizontal page scrolling; the process cycle may compact labels rather than forcing a wide rail.

## Error handling and privacy

- Worklet load errors identify the canonical worklet path and leave capture stopped.
- WebSocket disconnect, microphone track end, or device invalidation stops every active track and requires explicit recheck/restart.
- Capability and homepage status fetch failures render an explicit unavailable state.
- Graph computation failure must not interrupt transcript rendering.
- No microphone starts automatically and no speaker test is performed.
- Raw audio remains bounded in memory and is released by the existing realtime pipeline.
- Recordings, embeddings, transcripts, logs, runtime state, model weights, credentials, and private Agent state are not committed.

## Test strategy

### FastAPI and static contracts

- root page contains the three guide destinations and no recording controls;
- canonical `/asr_realtime` page and worklet are served correctly;
- old `/realtime` routes redirect;
- `/api/v1` and `/docs` remain unchanged.

### React unit and component tests

- start remains disabled until both Zone Vibe devices are ready;
- ordered server events select the correct active stage;
- the previous stage enters trail state and later becomes idle;
- reduced motion retains text state without animated emphasis;
- only completed utterances create graph nodes;
- late revision updates an existing node rather than duplicating it;
- newest/older node classes express a clear recency hierarchy;
- node position and visual transforms are separated and hover uses a fixed hit target;
- hovering a node exposes its corrected text without moving its position group.

### Verification

- full `./run.sh --test` baseline and final run;
- frontend production build;
- CPU container regression tests;
- NVIDIA rebuild/status verification on the current host;
- HTTP checks for `/`, `/docs`, `/asr_realtime`, canonical worklet, and `/realtime` redirect;
- manual browser smoke only after the user explicitly chooses to start microphone capture.

## Acceptance criteria

1. `http://127.0.0.1:8765/` is a concise project guide with API, realtime, and status destinations.
2. `http://127.0.0.1:8765/asr_realtime` loads the approved Apple-inspired realtime interface.
3. Device readiness is required before the listening control is enabled.
4. Actual Gateway events, not timers, drive the five-stage cycle.
5. Stage transitions preserve a visible fading afterglow and make the current stage unambiguous.
6. Corrected endpoints appear as stable interactive graph nodes with chronological and similarity edges.
7. Hover never changes node coordinates or jitters, and displays the node text.
8. Existing realtime ASR and correction behavior, `/api/v1`, `/docs`, and MCP contracts continue to pass tests.
