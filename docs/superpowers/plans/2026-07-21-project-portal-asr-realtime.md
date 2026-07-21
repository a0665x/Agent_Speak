# Project Portal and ASR Realtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved project-guide homepage and canonical `/asr_realtime` React experience using the existing realtime Gateway events, a device-gated listening loop, stage afterglow, and an interactive utterance text graph.

**Architecture:** Keep FastAPI responsible for static routing and preserve every `/api/v1` and MCP contract. Reuse the current AudioWorklet/WebSocket pipeline; extend the React reducer with an explicit semantic stage and completed utterance IDs, then render focused presentation components for the process cycle and graph. Compute bounded deterministic text-feature vectors in the browser behind a provider-shaped pure function so no new model or persisted embedding data is introduced.

**Tech Stack:** Python 3.11, FastAPI, React 19, TypeScript, Vite, Vitest, Testing Library, SVG, Web Audio AudioWorklet, WebSocket, CSS, pytest, Docker Compose.

---

## File map

- `src/agent_speak/app.py` — canonical and compatibility routes for the landing page and realtime static application.
- `tests/test_webui.py` — FastAPI/static route, landing-page, accessibility, and compatibility contracts.
- `web/index.html` — concise project-guide structure.
- `web/app.css` — Apple-inspired local visual system and responsive states.
- `web/app.js` — health/capability status only; no microphone behavior.
- `web/speech-core-hero.png` — generated local project artwork.
- `run.sh` — reports the canonical `/asr_realtime` URL.
- `frontend/realtime/vite.config.ts` — canonical Vite base and output directory.
- `frontend/realtime/src/audio/realtimeClient.ts` — canonical worklet URL.
- `frontend/realtime/src/types.ts` — ordered realtime event and pipeline-stage types.
- `frontend/realtime/src/state/reducer.ts` — event-to-stage mapping, transcript state, completion ledger, and session reset.
- `frontend/realtime/src/state/reducer.test.ts` — reducer mapping and completion tests.
- `frontend/realtime/src/components/ProcessCycle.tsx` — five-stage active/trail/idle presentation.
- `frontend/realtime/src/components/ProcessCycle.test.tsx` — afterglow and reduced-motion behavior.
- `frontend/realtime/src/graph/textGraph.ts` — deterministic feature vector, similarity, bounded nodes, edges, and stable coordinates.
- `frontend/realtime/src/graph/textGraph.test.ts` — vector, edge, bound, and coordinate tests.
- `frontend/realtime/src/components/UtteranceGraph.tsx` — stable layered SVG nodes and text tooltip.
- `frontend/realtime/src/components/UtteranceGraph.test.tsx` — node lifecycle, hover text, and no-jitter DOM contract.
- `frontend/realtime/src/App.tsx` — approved product composition and actual event integration.
- `frontend/realtime/src/App.test.tsx` — control gating and high-level event-driven surface.
- `frontend/realtime/src/styles.css` — final Apple-inspired motion, graph, device, and responsive styles.
- `spec/PROJECT_MAP.md`, `spec/UI.md`, `docs/OPENAPI_QUICKSTART_ZH_TW.md` — canonical route and UI documentation.

### Task 1: Canonical realtime route and compatibility redirects

**Files:**
- Modify: `tests/test_webui.py`
- Modify: `src/agent_speak/app.py`
- Modify: `frontend/realtime/vite.config.ts`
- Modify: `frontend/realtime/src/audio/realtimeClient.ts`
- Modify: `run.sh`

- [ ] **Step 1: Write failing canonical-route tests**

Replace the old additive route test with explicit canonical and redirect expectations:

```python
@pytest.mark.anyio
async def test_asr_realtime_is_canonical_and_old_route_redirects(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        canonical = await client.get("/asr_realtime")
        legacy = await client.get("/realtime")
        worklet = await client.get("/asr_realtime/pcm-capture.worklet.js")
    assert canonical.status_code == 200
    assert '<div id="root"></div>' in canonical.text
    assert legacy.status_code in {307, 308}
    assert legacy.headers["location"] == "/asr_realtime"
    assert worklet.headers["content-type"].startswith(("text/javascript", "application/javascript"))
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `pytest -q tests/test_webui.py::test_asr_realtime_is_canonical_and_old_route_redirects`
Expected: FAIL because `/asr_realtime` is not served and `/realtime` still returns 200.

- [ ] **Step 3: Implement canonical FastAPI routes**

In `src/agent_speak/app.py`, rename the static directory variable to `asr_realtime_web_dir`, mount `/asr_realtime/assets`, serve canonical index/worklet routes, and return `RedirectResponse` for legacy routes:

```python
from fastapi.responses import RedirectResponse

@app.get("/asr_realtime", include_in_schema=False)
@app.get("/asr_realtime/", include_in_schema=False)
async def asr_realtime_page() -> Response:
    return Response(
        content=(asr_realtime_web_dir / "index.html").read_text(encoding="utf-8"),
        media_type="text/html",
    )

@app.get("/realtime", include_in_schema=False)
async def legacy_realtime_page() -> RedirectResponse:
    return RedirectResponse("/asr_realtime", status_code=307)
```

Add canonical and redirect worklet routes with the same JavaScript content type.

- [ ] **Step 4: Update frontend and status paths**

Set Vite to:

```ts
base: '/asr_realtime/',
build: { outDir: '../../web/asr_realtime', emptyOutDir: true },
```

Change the AudioWorklet URL to `/asr_realtime/pcm-capture.worklet.js`, and update both URL strings in `run.sh` to `/asr_realtime`.

- [ ] **Step 5: Build and verify GREEN**

Run: `npm --prefix frontend/realtime run build && pytest -q tests/test_webui.py::test_asr_realtime_is_canonical_and_old_route_redirects`
Expected: Vite build succeeds and the focused pytest passes.

- [ ] **Step 6: Commit**

```bash
git add src/agent_speak/app.py tests/test_webui.py frontend/realtime/vite.config.ts frontend/realtime/src/audio/realtimeClient.ts run.sh web/asr_realtime
git commit -m "feat: make asr realtime the canonical demo route"
```

### Task 2: Project-guide homepage

**Files:**
- Modify: `tests/test_webui.py`
- Replace: `web/index.html`
- Replace: `web/app.css`
- Replace: `web/app.js`
- Create: `web/speech-core-hero.png`

- [ ] **Step 1: Replace legacy homepage tests with guide contracts**

Add tests that require the three destinations, forbid capture hooks, and check the status client:

```python
@pytest.mark.anyio
async def test_root_is_project_guide_without_capture_controls(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        page = (await client.get("/")).text
        javascript = (await client.get("/static/app.js")).text
    assert all(target in page for target in ('href="/docs"', 'href="/asr_realtime"', 'id="system-status"'))
    assert all(label in page for label in ("API Explorer", "ASR Realtime", "System Status"))
    assert "getUserMedia" not in javascript
    assert 'fetch("/api/v1/health")' in javascript
    assert 'fetch("/api/v1/capabilities")' in javascript
```

Update the old homepage accessibility test to require `:focus-visible`, 44 px targets, mobile layout, reduced motion, reduced transparency, and increased contrast.

- [ ] **Step 2: Run homepage tests and confirm RED**

Run: `pytest -q tests/test_webui.py -k 'root_is_project_guide or webui_css'`
Expected: FAIL because the legacy operator console is still present.

- [ ] **Step 3: Add generated artwork**

Copy the approved generated image into `web/speech-core-hero.png`. Do not add files from `.superpowers`, `.codex`, models, recordings, runtime, or logs.

- [ ] **Step 4: Implement the landing structure**

Create semantic local-only HTML with this core structure:

```html
<main id="main">
  <section class="hero" aria-labelledby="hero-title">…</section>
  <nav class="product-grid" aria-label="Project destinations">
    <a href="/docs">API Explorer</a>
    <a href="/asr_realtime">ASR Realtime</a>
    <section id="system-status" aria-live="polite">System Status</section>
  </nav>
  <section class="pipeline-preview" aria-label="Speech processing flow">…</section>
</main>
```

Keep copy short, use inline SVG icons, include fixed image dimensions/aspect ratio and useful Chinese alt text, and retain the skip link.

- [ ] **Step 5: Implement visual states and status fetch**

Use CSS variables for graphite, ice blue, and violet; provide hover and `:active` feedback without delaying navigation. In `web/app.js`, fetch health and capabilities concurrently, render provider/model/device values through `textContent`, and show an unavailable state on failure. Do not use `innerHTML`, microphone APIs, WebSocket, Agent, TTS, or external assets.

- [ ] **Step 6: Run homepage tests and commit**

Run: `pytest -q tests/test_webui.py -k 'root_is_project_guide or webui_css'`
Expected: PASS.

```bash
git add tests/test_webui.py web/index.html web/app.css web/app.js web/speech-core-hero.png
git commit -m "feat: replace homepage with project guide"
```

### Task 3: Event-driven five-stage reducer

**Files:**
- Modify: `frontend/realtime/src/types.ts`
- Modify: `frontend/realtime/src/state/reducer.ts`
- Modify: `frontend/realtime/src/state/reducer.test.ts`

- [ ] **Step 1: Write failing reducer tests**

Add a helper event factory and assert semantic mappings plus completed IDs:

```ts
test.each([
  ['stream.started', {}, 'listening'],
  ['vad.speech_started', {}, 'voice'],
  ['asr.partial', { text: '測試' }, 'asr'],
  ['endpoint.candidate', { silence_ms: 900 }, 'endpoint'],
  ['correction.processing', {}, 'correction'],
])('maps %s to %s', (type, data, stage) => {
  const next = realtimeReducer(initialState, event(type, data));
  expect(next.stage).toBe(stage);
});

test('records one completed utterance and resets for a new client session', () => {
  const completed = realtimeReducer(initialState, event('utterance.completed', {}, 'u-1'));
  expect(completed.completedUtteranceIds).toEqual(['u-1']);
  expect(realtimeReducer(completed, { type: 'client.session_reset' })).toEqual(initialState);
});
```

- [ ] **Step 2: Run reducer tests and confirm RED**

Run: `npm --prefix frontend/realtime test -- src/state/reducer.test.ts`
Expected: FAIL because `stage`, completion IDs, and the reset action do not exist.

- [ ] **Step 3: Implement types and reducer mapping**

Add:

```ts
export type PipelineStage = 'idle' | 'listening' | 'voice' | 'asr' | 'endpoint' | 'correction' | 'error';
export type RealtimeAction = RealtimeEvent | { type: 'client.session_reset' };
```

Extend state with `stage` and `completedUtteranceIds`. Handle the exact event mapping from the approved design, append a non-duplicate `utterance_id` on completion, preserve final ASR text on correction errors, and reset only on the explicit client action.

- [ ] **Step 4: Run reducer tests and commit**

Run: `npm --prefix frontend/realtime test -- src/state/reducer.test.ts`
Expected: PASS.

```bash
git add frontend/realtime/src/types.ts frontend/realtime/src/state/reducer.ts frontend/realtime/src/state/reducer.test.ts
git commit -m "feat: model realtime processing stages"
```

### Task 4: Process cycle with interruptible afterglow

**Files:**
- Create: `frontend/realtime/src/components/ProcessCycle.tsx`
- Create: `frontend/realtime/src/components/ProcessCycle.test.tsx`

- [ ] **Step 1: Write failing component tests**

```tsx
test('keeps the previous stage as a trail while the current stage is active', () => {
  vi.useFakeTimers();
  const view = render(<ProcessCycle stage="voice" reducedMotion={false} />);
  view.rerender(<ProcessCycle stage="asr" reducedMotion={false} />);
  expect(screen.getByTestId('stage-asr')).toHaveAttribute('data-state', 'active');
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'trail');
  act(() => vi.advanceTimersByTime(1500));
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'idle');
});

test('reduced motion keeps semantic state without trail animation', () => {
  const view = render(<ProcessCycle stage="voice" reducedMotion />);
  view.rerender(<ProcessCycle stage="asr" reducedMotion />);
  expect(screen.getByTestId('stage-asr')).toHaveAttribute('data-state', 'active');
  expect(screen.getByTestId('stage-voice')).toHaveAttribute('data-state', 'idle');
});
```

- [ ] **Step 2: Run the new test and confirm RED**

Run: `npm --prefix frontend/realtime test -- src/components/ProcessCycle.test.tsx`
Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the component**

Render the five fixed stages with Lucide icons. Track the previous non-idle stage in an effect, expose `data-state="active|trail|idle"`, and clear the trail after 1,450 ms. Clear/restart the timeout on rapid transitions and clear it on unmount. The timer controls presentation only; it never advances the semantic stage.

- [ ] **Step 4: Run component tests and commit**

Run: `npm --prefix frontend/realtime test -- src/components/ProcessCycle.test.tsx`
Expected: PASS.

```bash
git add frontend/realtime/src/components/ProcessCycle.tsx frontend/realtime/src/components/ProcessCycle.test.tsx
git commit -m "feat: add event-driven process cycle"
```

### Task 5: Bounded local text graph model

**Files:**
- Create: `frontend/realtime/src/graph/textGraph.ts`
- Create: `frontend/realtime/src/graph/textGraph.test.ts`

- [ ] **Step 1: Write failing pure-model tests**

```ts
test('produces deterministic normalized feature vectors', () => {
  const first = embedText('即時語音辨識');
  const second = embedText('即時語音辨識');
  expect(first).toEqual(second);
  expect(Math.hypot(...first)).toBeCloseTo(1, 5);
});

test('keeps coordinates stable and bounds the graph', () => {
  const first = buildTextGraph(rows(3), 24);
  const next = buildTextGraph(rows(4), 24);
  expect(next.nodes.slice(0, 3).map(node => [node.x, node.y])).toEqual(
    first.nodes.map(node => [node.x, node.y])
  );
  expect(buildTextGraph(rows(30), 24).nodes).toHaveLength(24);
});

test('adds chronological edges and only thresholded similarity edges', () => {
  const graph = buildTextGraph(sampleRows, 24);
  expect(graph.edges.filter(edge => edge.kind === 'timeline')).toHaveLength(graph.nodes.length - 1);
  expect(graph.edges.filter(edge => edge.kind === 'similarity').every(edge => edge.score >= .42)).toBe(true);
});
```

- [ ] **Step 2: Run graph-model tests and confirm RED**

Run: `npm --prefix frontend/realtime test -- src/graph/textGraph.test.ts`
Expected: FAIL because the graph model does not exist.

- [ ] **Step 3: Implement deterministic vectors and graph building**

Implement Unicode normalization, Mandarin/Latin/number unigrams and adjacent bi-grams, signed FNV-style hashing into 96 dimensions, L2 normalization, cosine similarity, stable grid coordinates, solid consecutive edges, and at most two thresholded similarity edges for each node. Slice to the newest `maxNodes` before layout.

- [ ] **Step 4: Run graph tests and commit**

Run: `npm --prefix frontend/realtime test -- src/graph/textGraph.test.ts`
Expected: PASS.

```bash
git add frontend/realtime/src/graph/textGraph.ts frontend/realtime/src/graph/textGraph.test.ts
git commit -m "feat: add bounded local utterance graph model"
```

### Task 6: Stable interactive utterance graph

**Files:**
- Create: `frontend/realtime/src/components/UtteranceGraph.tsx`
- Create: `frontend/realtime/src/components/UtteranceGraph.test.tsx`

- [ ] **Step 1: Write failing SVG interaction tests**

```tsx
test('renders only completed utterances with layered stable nodes', () => {
  render(<UtteranceGraph rows={rows} completedUtteranceIds={['u-1']} />);
  const node = screen.getByTestId('graph-node-u-1');
  expect(node).toHaveAttribute('transform', expect.stringMatching(/^translate\(/));
  expect(within(node).getByTestId('node-hit-u-1')).toHaveAttribute('r', '36');
  expect(within(node).getByTestId('node-visual-u-1')).not.toHaveAttribute('transform');
  expect(screen.queryByTestId('graph-node-u-2')).not.toBeInTheDocument();
});

test('hover shows corrected text without changing position transform', async () => {
  const user = userEvent.setup();
  render(<UtteranceGraph rows={rows} completedUtteranceIds={['u-1']} />);
  const node = screen.getByTestId('graph-node-u-1');
  const before = node.getAttribute('transform');
  await user.hover(screen.getByTestId('node-hit-u-1'));
  expect(screen.getByRole('tooltip')).toHaveTextContent(rows[0].text);
  expect(node).toHaveAttribute('transform', before);
});
```

- [ ] **Step 2: Run graph component tests and confirm RED**

Run: `npm --prefix frontend/realtime test -- src/components/UtteranceGraph.test.tsx`
Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement layered SVG and tooltip**

Build graph input by joining completed IDs with current transcript rows. Render edge lines first. Each node must use a translated outer `<g>`, a fixed transparent hit circle, and a pointer-events-disabled inner visual `<g>`. Track hovered ID in React state; apply hover class only to the visual layer and render tooltip text as a React text node. Apply `new`, `recent`, and `history` classes by recency without changing coordinates.

- [ ] **Step 4: Run component tests and commit**

Run: `npm --prefix frontend/realtime test -- src/components/UtteranceGraph.test.tsx`
Expected: PASS.

```bash
git add frontend/realtime/src/components/UtteranceGraph.tsx frontend/realtime/src/components/UtteranceGraph.test.tsx
git commit -m "feat: visualize completed asr utterances"
```

### Task 7: Compose approved realtime product UI

**Files:**
- Modify: `frontend/realtime/src/App.test.tsx`
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/components/DeviceGate.tsx`
- Modify: `frontend/realtime/src/styles.css`

- [ ] **Step 1: Extend high-level UI tests**

Mock the realtime client boundary and verify that the page renders the new headline, five-stage cycle, disabled start control, and empty graph without requesting devices on mount. Add a reducer-driven fixture test that renders a completed row in the graph and asserts the newest node class.

- [ ] **Step 2: Run App tests and confirm RED**

Run: `npm --prefix frontend/realtime test -- src/App.test.tsx`
Expected: FAIL because the approved layout and components are not composed.

- [ ] **Step 3: Compose the page**

In `App.tsx`:

```tsx
<ProcessCycle stage={state.stage} reducedMotion={reducedMotion} />
<AudioStage samples={envelope} state={state.stream} />
<TranscriptPanel rows={state.rows} />
<UtteranceGraph rows={state.rows} completedUtteranceIds={state.completedUtteranceIds} />
```

Dispatch `{ type: 'client.session_reset' }` immediately before creating a new session. Keep the existing capability fetch, device gate, explicit start/stop handlers, error handling, and `aria-live` status. Remove the legacy information-dense side rail only where the new five-stage cycle replaces it; retain truthful worker/model diagnostics in a compact card.

- [ ] **Step 4: Implement final CSS**

Use the approved graphite/ice-blue/violet palette, oversized gradient background words, short hero copy, translucent cards, 100 ms press feedback, current-stage halo, 1,450 ms trail fade, stable graph hover scaling on the inner group only, and strong new/history opacity contrast. Add mobile, reduced-motion, reduced-transparency, and increased-contrast media queries.

- [ ] **Step 5: Run the complete frontend suite and build**

Run: `npm --prefix frontend/realtime test && npm --prefix frontend/realtime run build`
Expected: all Vitest tests pass and production assets are emitted to `web/asr_realtime`.

- [ ] **Step 6: Commit**

```bash
git add frontend/realtime/src web/asr_realtime
git commit -m "feat: ship apple inspired asr realtime experience"
```

### Task 8: Documentation and end-to-end verification

**Files:**
- Modify: `spec/PROJECT_MAP.md`
- Modify: `spec/UI.md`
- Modify: `docs/OPENAPI_QUICKSTART_ZH_TW.md`

- [ ] **Step 1: Update canonical route documentation**

Replace `/realtime` references that describe the canonical UI with `/asr_realtime`, document the legacy redirect, the five-stage event-driven cycle, the device gate, and the bounded local text-similarity graph. Preserve the external-Agent contract `listen_once → external reasoning/tools → speak` and state that this page does not invoke Agent/TTS.

- [ ] **Step 2: Run focused and full verification**

Run:

```bash
git diff --check
npm --prefix frontend/realtime test
npm --prefix frontend/realtime run build
./run.sh --test
```

Expected: no whitespace errors, all frontend tests pass, Vite builds, and `TESTS_OK` is printed.

- [ ] **Step 3: Rebuild and start the approved runtime**

Run: `AGENT_SPEAK_ACCELERATOR=auto ./run.sh --rebuild`
Expected: NVIDIA preflight selects `nvidia`; gateway, ASR worker, and correction worker become healthy.

- [ ] **Step 4: Verify live URLs without starting hardware**

Run:

```bash
curl -fsS http://127.0.0.1:8765/api/v1/health
curl -fsS http://127.0.0.1:8765/
curl -fsS http://127.0.0.1:8765/asr_realtime
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:8765/realtime
curl -fsS http://127.0.0.1:8765/docs
./run.sh --status
```

Expected: health is ready, root and canonical UI return 200, legacy route redirects to `/asr_realtime`, docs return 200, and status reports NVIDIA/CUDA with the canonical URL.

- [ ] **Step 5: Commit documentation and final generated assets**

```bash
git add spec/PROJECT_MAP.md spec/UI.md docs/OPENAPI_QUICKSTART_ZH_TW.md
git commit -m "docs: publish asr realtime project routes"
```

No microphone or speaker test is run automatically. The operator performs the final capture smoke by opening `/asr_realtime`, pressing **Check devices**, and then explicitly pressing **Start Listening**.
