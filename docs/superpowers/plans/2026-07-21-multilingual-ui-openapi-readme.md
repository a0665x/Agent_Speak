# Multilingual UI, OpenAPI, and README Visual Tour Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an English-default, four-language Agent Speak portal, ASR Realtime studio, and fully localized Swagger contract, then publish an English README visual tour built from real local screenshots.

**Architecture:** Keep `/api/v1` runtime behavior unchanged. Share locale identifiers and resolution semantics across a build-free portal utility, a typed React context, and a Python OpenAPI metadata overlay; custom `/docs` loads the selected `/openapi.json?lang=...` document. Capture safe read-only English UI states from the running service, retain each PNG, and assemble an optimized animated GIF for GitHub.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest, vanilla HTML/CSS/JavaScript, React 19, TypeScript, Vite, Vitest, Testing Library, Google Chrome headless, ffmpeg, Docker Compose, Markdown.

---

## File Structure

- Create `src/agent_speak/locales.py`: supported locales, locale normalization, translated API/tag/operation/model-field catalogs, and OpenAPI metadata overlay.
- Modify `src/agent_speak/app.py`: English canonical route metadata, localized OpenAPI endpoint, custom localized Swagger page, and static docs-locale assets.
- Create `web/locale.js`: portal locale resolution, persistence, catalog lookup, DOM translation, and localized navigation.
- Modify `web/index.html`, `web/app.js`, and `web/app.css`: English source markup, stable translation keys, language selector, localized dynamic status, and responsive selector styling.
- Create `web/docs-locale.js` and `web/docs-locale.css`: Swagger language selector behavior and styling.
- Create `frontend/realtime/src/i18n.tsx`: typed locale catalog, resolver, provider, hook, and localized-link helper.
- Modify React application/component files: replace human copy with typed catalog lookups while leaving reducer/audio/graph data behavior unchanged.
- Modify Python and frontend tests: cover locale completeness, fallback, propagation, translated UI, and OpenAPI structural identity.
- Modify `spec/API.md`, `spec/UI.md`, `spec/PROJECT_MAP.md`, `README.md`, and `README.zh-TW.md`: publish the new language and route behavior.
- Create `docs/screenshots/*.png` and `docs/screenshots/agent-speak-tour.gif`: real English product layers and GitHub-compatible carousel.

### Task 1: Python Locale Contract and OpenAPI Overlay

**Files:**
- Create: `src/agent_speak/locales.py`
- Modify: `src/agent_speak/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing locale and schema tests**

Add tests that request `/openapi.json`, `/openapi.json?lang=zh-TW`, `?lang=ja`, `?lang=ko`, and `?lang=invalid`. Assert English is the default, invalid input falls back to English, localized endpoint summaries differ, and structural API data remains identical after recursively removing `title`, `description`, `summary`, `example`, `examples`, and tag display names.

```python
@pytest.mark.parametrize("locale, expected", [
    ("en", "Check service health"),
    ("zh-TW", "檢查服務健康狀態"),
    ("ja", "サービスの稼働状態を確認"),
    ("ko", "서비스 상태 확인"),
])
def test_openapi_localizes_every_supported_language(client, locale, expected):
    schema = client.get(f"/openapi.json?lang={locale}").json()
    assert schema["paths"]["/api/v1/health"]["get"]["summary"] == expected
    assert schema["components"]["schemas"]["HealthResponse"]["properties"]["storage_ready"]["description"]
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `./run.sh --test tests/test_app.py -k 'openapi and local'` if argument forwarding is supported; otherwise run `docker compose -f compose.yaml run --rm gateway-test pytest -vv tests/test_app.py -k 'openapi and local'`.

Expected: FAIL because the current OpenAPI metadata is Traditional Chinese and ignores `lang`.

- [ ] **Step 3: Implement locale primitives and complete catalogs**

Create immutable locale primitives with exact supported identifiers and English fallback:

```python
SUPPORTED_LOCALES = ("en", "zh-TW", "ja", "ko")
DEFAULT_LOCALE = "en"

def normalize_locale(value: str | None) -> str:
    return value if value in SUPPORTED_LOCALES else DEFAULT_LOCALE
```

Define catalog sections for API info, six stable semantic tags (`system`, `conversation`, `audio`, `text`, `speakers`, `artifacts`), all 19 HTTP operations keyed by `METHOD /path`, the PCM WAV request body, query/path parameters, and every Pydantic component/property in `schemas.py`. Each locale must contain the same semantic keys. English examples are canonical; natural-language examples are translated while identifiers and machine values stay unchanged.

- [ ] **Step 4: Generate a localized schema without mutating the canonical cache**

Use `fastapi.openapi.utils.get_openapi`, deep-copy the canonical schema, apply translated metadata by stable path/method and component/property keys, and cache one completed dictionary per supported locale. Keep path names, operation IDs, types, constraints, required lists, response codes, and content types untouched.

```python
def localize_openapi(schema: dict[str, Any], locale: str) -> dict[str, Any]:
    localized = deepcopy(schema)
    language = normalize_locale(locale)
    catalog = OPENAPI_CATALOGS[language]
    localized["info"].update(catalog["info"])
    localized["tags"] = [catalog["tags"][key] for key in TAG_KEYS]
    for operation_key, metadata in catalog["operations"].items():
        method, path = operation_key.split(" ", 1)
        localized["paths"][path][method.lower()].update(metadata)
    for schema_name, fields in catalog["fields"].items():
        properties = localized["components"]["schemas"][schema_name]["properties"]
        for field_name, description in fields.items():
            properties[field_name]["description"] = description
    return localized
```

- [ ] **Step 5: Serve English by default and localized variants by query**

Disable FastAPI's generated OpenAPI route with `openapi_url=None`, keep an internal canonical schema builder, and add an excluded `GET /openapi.json` route accepting `lang: str | None`. Return a JSON response from the per-locale cache. Convert decorator tags in `app.py` to stable English names so generation starts from the English contract.

- [ ] **Step 6: Run focused and contract tests**

Run: `docker compose -f compose.yaml run --rm gateway-test pytest -vv tests/test_app.py tests/test_contracts.py tests/test_docs.py`

Expected: PASS with all API paths and response models unchanged.

- [ ] **Step 7: Commit the OpenAPI locale layer**

```bash
git add src/agent_speak/locales.py src/agent_speak/app.py tests/test_app.py tests/test_contracts.py tests/test_docs.py
git commit -m "feat: localize openapi metadata"
```

### Task 2: Localized Swagger Surface

**Files:**
- Create: `web/docs-locale.js`
- Create: `web/docs-locale.css`
- Modify: `src/agent_speak/app.py`
- Modify: `tests/test_webui.py`

- [ ] **Step 1: Write failing Swagger locale tests**

Assert `/docs` defaults to English, `/docs?lang=ja` sets `<html lang="ja">`, the page includes a top-right `<select id="language-select">`, all four option values, local script/style assets, and a Swagger initializer URL of `/openapi.json?lang=ja`. Assert unknown locale selects English.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `docker compose -f compose.yaml run --rm gateway-test pytest -vv tests/test_webui.py -k docs_language`

Expected: FAIL because FastAPI's stock Swagger page has no language selector.

- [ ] **Step 3: Implement custom Swagger HTML**

Set `docs_url=None`. Add an excluded `/docs` route that normalizes `lang`, returns CSP-compatible HTML, loads Swagger UI's existing jsDelivr bundle, initializes `SwaggerUIBundle({url: '/openapi.json?lang=<locale>', dom_id: '#swagger-ui'})`, and renders the same four-language selector in the top-right toolbar.

- [ ] **Step 4: Implement selector persistence and navigation**

`web/docs-locale.js` reads `data-current-locale`, writes `agent-speak-locale` to localStorage, and replaces the current URL with `/docs?lang=${encodeURIComponent(locale)}`. The script must use `textContent`/DOM APIs only. Style the selector for desktop/mobile, focus-visible, hover, and active states without obscuring Swagger controls.

- [ ] **Step 5: Run docs CSP and browser-contract tests**

Run: `docker compose -f compose.yaml run --rm gateway-test pytest -vv tests/test_webui.py tests/test_app.py -k 'docs or openapi'`

Expected: PASS; `/docs` retains its docs-specific CSP and `/` retains the strict self-only CSP.

- [ ] **Step 6: Commit Swagger localization**

```bash
git add src/agent_speak/app.py web/docs-locale.js web/docs-locale.css tests/test_webui.py tests/test_app.py
git commit -m "feat: add multilingual swagger explorer"
```

### Task 3: English-Default Four-Language Project Portal

**Files:**
- Create: `web/locale.js`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/app.css`
- Modify: `tests/test_webui.py`
- Test: `tests/portal_locale.test.js`

- [ ] **Step 1: Write failing portal locale tests**

Test query-over-storage resolution, English fallback, all catalog keys in all locales, localized links, and status wording. Extend server HTML tests to require `<html lang="en">`, `#language-select`, and English hero text.

```javascript
assert.equal(resolveLocale('?lang=ja', 'zh-TW'), 'ja');
assert.equal(resolveLocale('', 'ko'), 'ko');
assert.equal(resolveLocale('?lang=xx', 'zh-TW'), 'en');
assert.equal(withLocale('/docs', 'ko'), '/docs?lang=ko');
```

- [ ] **Step 2: Run tests and verify failure**

Run: `node --test tests/portal_locale.test.js` and the focused `tests/test_webui.py` portal tests.

Expected: FAIL because the utility and English default do not exist.

- [ ] **Step 3: Implement portal locale utility and complete catalog**

Export testable `SUPPORTED_LOCALES`, `resolveLocale`, `withLocale`, `translate`, and `applyLocale`. Catalog all metadata, skip/navigation, hero, cards, status states, pipeline, image alternative text, and footer copy in English, Traditional Chinese, Japanese, and Korean. Missing keys return the English value.

- [ ] **Step 4: Convert portal markup to English keyed content**

Set source `<html lang="en">`; add `data-i18n`, `data-i18n-aria-label`, and `data-i18n-alt` keys. Add the top-right selector with values `en`, `zh-TW`, `ja`, and `ko`. Ensure `/asr_realtime` and `/docs` destinations receive the selected query value.

- [ ] **Step 5: Localize dynamic system status**

Resolve the locale before the API requests and render loading, ready, down, and unavailable strings from the catalog. Keep provider names/devices and health versions as received.

- [ ] **Step 6: Style and verify selector interaction**

Add stable-width glass styling, hover/active transitions, visible keyboard focus, reduced-motion behavior, and a mobile layout that does not overflow at 360 px.

- [ ] **Step 7: Run portal tests and commit**

Run: `node --test tests/portal_locale.test.js` plus `docker compose -f compose.yaml run --rm gateway-test pytest -vv tests/test_webui.py -k 'portal or homepage'`.

```bash
git add web/index.html web/app.js web/app.css web/locale.js tests/portal_locale.test.js tests/test_webui.py
git commit -m "feat: add multilingual project portal"
```

### Task 4: Typed ASR Realtime Locale Foundation

**Files:**
- Create: `frontend/realtime/src/i18n.tsx`
- Create: `frontend/realtime/src/i18n.test.tsx`
- Modify: `frontend/realtime/src/main.tsx`
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/styles.css`

- [ ] **Step 1: Write failing locale provider tests**

Assert default English, query-over-storage resolution, invalid-query English fallback, catalog completeness, document language updates, persisted selection, and localized navigation URLs.

- [ ] **Step 2: Run Vitest and verify failure**

Run: `npm test -- --run src/i18n.test.tsx` from `frontend/realtime`.

Expected: FAIL because `i18n.tsx` does not exist.

- [ ] **Step 3: Implement typed catalog and provider**

Define `type Locale = 'en' | 'zh-TW' | 'ja' | 'ko'`, a canonical English object, and `satisfies Record<Locale, Record<MessageKey, string>>`. Implement `I18nProvider`, `useI18n()`, and `localizedHref(path, locale)`; update `document.documentElement.lang` and `localStorage` only in effects/event handlers.

- [ ] **Step 4: Add the ASR Realtime selector and localize App copy**

Wrap the application in `I18nProvider`. Add the top-right selector beside `ASR REALTIME · LOCAL`, localize headings, session labels, device-check/start/stop controls, model/queue labels, warning/error guidance, and live-region text. Keep provider names, session ID, endpoint values, and server transcript text unchanged.

- [ ] **Step 5: Style responsive and accessible interaction states**

Match the portal selector, preserve the current Apple-inspired navigation, add `:hover`, `:active`, and `:focus-visible`, and confirm the control remains usable with reduced motion and at mobile width.

- [ ] **Step 6: Run tests and commit**

Run: `npm test -- --run src/i18n.test.tsx src/App.test.tsx`.

```bash
git add frontend/realtime/src/i18n.tsx frontend/realtime/src/i18n.test.tsx frontend/realtime/src/main.tsx frontend/realtime/src/App.tsx frontend/realtime/src/styles.css frontend/realtime/src/App.test.tsx
git commit -m "feat: add realtime language foundation"
```

### Task 5: Localize Every Realtime Presentation Layer

**Files:**
- Modify: `frontend/realtime/src/components/AudioStage.tsx`
- Modify: `frontend/realtime/src/components/DeviceGate.tsx`
- Modify: `frontend/realtime/src/components/PipelineRail.tsx`
- Modify: `frontend/realtime/src/components/ProcessCycle.tsx`
- Modify: `frontend/realtime/src/components/TranscriptPanel.tsx`
- Modify: `frontend/realtime/src/components/UtteranceGraph.tsx`
- Modify: corresponding `*.test.tsx` files and `frontend/realtime/src/App.test.tsx`

- [ ] **Step 1: Write failing component translation tests**

Render representative components inside `I18nProvider` with each locale and assert translated process stages, device empty states, transcript statuses, graph heading/legend/empty state/tooltips, audio states, and inference labels. Retain existing stage-trail and graph-position stability assertions.

- [ ] **Step 2: Run component tests and verify failure**

Run: `npm test -- --run src/components src/App.test.tsx` from `frontend/realtime`.

Expected: FAIL because components still contain mixed English/Chinese literals.

- [ ] **Step 3: Replace component literals with typed keys**

Use `const { t } = useI18n()` in each presentation component. Map enum-like states to explicit message keys rather than constructing keys dynamically. Keep DOM structure, CSS classes, `data-state`, SVG transforms, pointer hit areas, and realtime event semantics unchanged.

- [ ] **Step 4: Verify all four locale catalogs are complete**

The catalog test iterates `Object.keys(messages.en)` and asserts every locale owns each key and each value is non-empty. Ensure Japanese and Korean strings are natural and concise enough for the existing cards.

- [ ] **Step 5: Run full frontend tests and production build**

Run: `npm test -- --run` and `npm run build` from `frontend/realtime`.

Expected: all Vitest files pass and Vite writes hashed assets under `web/asr_realtime`.

- [ ] **Step 6: Commit complete realtime localization**

```bash
git add frontend/realtime/src frontend/realtime/package-lock.json web/asr_realtime
git commit -m "feat: localize realtime experience"
```

### Task 6: Update Canonical Specifications and Operator Docs

**Files:**
- Modify: `spec/API.md`
- Modify: `spec/UI.md`
- Modify: `spec/PROJECT_MAP.md`
- Modify: `spec/TESTING.md`
- Modify: `README.zh-TW.md`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Write failing documentation-contract assertions**

Require the specs to name all four locale identifiers, English default behavior, `/openapi.json?lang=`, `/docs?lang=`, and the unchanged `/api/v1` contract.

- [ ] **Step 2: Run docs tests and verify failure**

Run: `docker compose -f compose.yaml run --rm gateway-test pytest -vv tests/test_docs.py tests/test_operations.py`

Expected: FAIL because canonical specs still describe a Traditional-Chinese-first UI and schema.

- [ ] **Step 3: Update canonical documentation**

Document the locale precedence, custom Swagger behavior, translated metadata boundary, route propagation, screenshot safety rule, and English source-of-truth policy. Correct `/realtime` references to canonical `/asr_realtime` while preserving the redirect note.

- [ ] **Step 4: Run docs tests and commit**

```bash
git add spec/API.md spec/UI.md spec/PROJECT_MAP.md spec/TESTING.md README.zh-TW.md tests/test_docs.py tests/test_operations.py
git commit -m "docs: publish multilingual interface contract"
```

### Task 7: Capture English Product Layers and Build the Carousel

**Files:**
- Create: `docs/screenshots/01-project-home-hero.png`
- Create: `docs/screenshots/02-project-home-destinations.png`
- Create: `docs/screenshots/03-project-home-pipeline.png`
- Create: `docs/screenshots/04-asr-realtime-device-gate.png`
- Create: `docs/screenshots/05-asr-realtime-process-cycle.png`
- Create: `docs/screenshots/06-asr-realtime-transcript.png`
- Create: `docs/screenshots/07-asr-realtime-utterance-graph.png`
- Create: `docs/screenshots/08-api-explorer.png`
- Create: `docs/screenshots/agent-speak-tour.gif`
- Create: `scripts/capture_readme_screenshots.sh`

- [ ] **Step 1: Add a deterministic capture script**

The script verifies health first, creates only `docs/screenshots`, launches headless Google Chrome with a fixed 1440 px viewport against `/?lang=en`, `/asr_realtime?lang=en`, and `/docs?lang=en`, waits for fonts/status/Swagger rendering, and captures full-page sources. It then uses ffmpeg crops/scales to produce the eight named PNGs. It must not click device-check or listening controls and must never grant microphone permission.

- [ ] **Step 2: Run the capture against the live stack**

Run: `./scripts/capture_readme_screenshots.sh`

Expected: eight non-empty English PNG files; no microphone permission indicator and no new runtime audio artifact.

- [ ] **Step 3: Inspect every PNG visually**

Open all eight images, confirm English copy, correct crop boundaries, no loading/error overlay, no clipped selector, stable graph area, readable Swagger content, and no private identifiers beyond normal local provider/model status.

- [ ] **Step 4: Build an optimized animated GIF**

Use ffmpeg with a generated palette, 1440 px maximum width, a readable hold per frame, and a short crossfade or clean cut. Target a practical GitHub size while retaining readable headings. Verify with `ffprobe` that the GIF is animated and includes all eight frames.

- [ ] **Step 5: Commit capture tooling and assets**

```bash
git add scripts/capture_readme_screenshots.sh docs/screenshots
git commit -m "docs: capture multilingual product tour"
```

### Task 8: Refresh the English README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the English product introduction and routes**

Lead with the local, agent-agnostic speech gateway outcome; present Project Home, API Explorer, and ASR Realtime links; change the canonical realtime route to `/asr_realtime`; explain English-default four-language switching and localized Swagger URLs.

- [ ] **Step 2: Add the GitHub-compatible Photo Carousel**

Embed `docs/screenshots/agent-speak-tour.gif` with descriptive English alt text and a short note that the animation shows read-only English product layers without microphone activation.

- [ ] **Step 3: Add the clickable PNG gallery**

Use a compact two-column HTML table. Each thumbnail links to its original PNG and has an English title covering Portal Hero, Destinations, Local Pipeline, Device Gate, Processing Cycle, Transcript, Utterance Graph, and API Explorer.

- [ ] **Step 4: Validate links, images, and README wording**

Check every relative asset path exists, no `/realtime` canonical claim remains, language URLs are correct, and README contains no claim that the development echo is a real LLM.

- [ ] **Step 5: Commit README**

```bash
git add README.md
git commit -m "docs: add english product carousel"
```

### Task 9: Full Verification and Direct Main Push

**Files:**
- Verify all intended files only; do not add `.superpowers/` or private/runtime data.

- [ ] **Step 1: Run the complete project suite**

Run: `./run.sh --test`

Expected: Python, Node, and frontend suites finish with `TESTS_OK`.

- [ ] **Step 2: Rebuild/restart and verify live routes**

Run the approved auto-accelerator rebuild/start flow, then `./run.sh --status`. Verify `/`, `/asr_realtime`, `/docs?lang=ja`, and all four `/openapi.json?lang=` variants return successfully. Confirm `/realtime` still redirects.

- [ ] **Step 3: Inspect Git hygiene and final diff**

Run `git diff --check`, `git status --short --branch`, `git diff origin/main...HEAD --stat`, and inspect staged/tracked screenshot sizes. Confirm `.superpowers/`, `.env`, recordings, voice features, databases, runtime, models, weights, logs, and credentials are absent.

- [ ] **Step 4: Verify GitHub CLI and push scope**

Run `gh --version`, `gh auth status`, `git remote -v`, and `git log --oneline origin/main..HEAD`. The push intentionally includes the existing unpublished `main` commits plus this feature, as authorized in the approved design.

- [ ] **Step 5: Push directly to main**

Run: `git push origin main`

Expected: `origin/main` advances to the verified local `main` HEAD.

- [ ] **Step 6: Confirm remote state**

Run: `git status --short --branch` and `git ls-remote --heads origin main`.

Expected: local `main` is aligned with `origin/main`; only explicitly excluded local files may remain untracked.
