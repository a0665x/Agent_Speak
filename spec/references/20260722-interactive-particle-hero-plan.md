# Interactive Particle Hero Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the homepage and ASR messaging and add a shared, accessible, pointer-responsive particle field with page-specific visual intensity.

**Architecture:** A UMD-style `web/particle-field.js` exports pure layout/motion functions for Node tests and exposes a browser mount API. The homepage mounts it directly; a small React component mounts the same API for ASR and replaces the previous full-screen line-wave renderer.

**Tech Stack:** Canvas 2D, browser JavaScript, React 19, TypeScript, Node test runner, Vitest, Vite, FastAPI static routes.

---

### Task 1: Lock localized messaging and page hooks

**Files:**
- Modify: `tests/portal_locale.test.js`
- Modify: `tests/test_webui.py`
- Modify: `frontend/realtime/src/i18n.test.tsx`
- Modify: `frontend/realtime/src/App.test.tsx`

- [ ] Write failing tests for the English-default and Traditional Chinese homepage hero, all four complete locale catalogs, localized ASR title/copy, document title, homepage particle canvas, ASR subtle particle canvas, and `/static/particle-field.js`.
- [ ] Run the focused Node, Pytest, and Vitest tests and confirm failures identify missing copy, canvas hooks, and static asset.

### Task 2: Implement the shared particle engine

**Files:**
- Create: `web/particle-field.js`
- Create: `tests/particle_field.test.js`
- Modify: `src/agent_speak/app.py`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/app.css`

- [ ] Add failing pure tests for deterministic bounded point generation, stronger homepage versus subtle ASR profiles, pointer displacement radius, and spring return.
- [ ] Implement the smallest pure functions that pass those tests, then add the Canvas mount lifecycle, resize handling, visibility pause, pointer tracking, capped DPR, and reduced-motion static frame.
- [ ] Serve the shared asset, add the homepage canvas, mount it with the primary profile, and place it between the background gradients and content without changing click targets.
- [ ] Run the particle, portal, and web route tests until green.

### Task 3: Integrate ASR particles and four-language titles

**Files:**
- Create: `frontend/realtime/src/components/ParticleField.tsx`
- Create: `frontend/realtime/src/components/ParticleField.test.tsx`
- Modify: `frontend/realtime/index.html`
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/i18n.tsx`
- Modify: `frontend/realtime/src/styles.css`
- Delete: `frontend/realtime/src/vendor/reactbits/Waves.tsx`
- Delete: `frontend/realtime/src/vendor/reactbits/Waves.css`

- [ ] Implement a React lifecycle wrapper around the shared browser mount API and render the subtle profile behind ASR content.
- [ ] Replace the ASR hero and document metadata in English, Traditional Chinese, Japanese, and Korean.
- [ ] Remove the old line-wave renderer so only one full-screen animation loop remains.
- [ ] Run focused component/i18n tests, the complete Vitest suite, and `npm run build`.

### Task 4: Verify, document, deploy, and publish

**Files:**
- Modify: `spec/PROJECT_MAP.md`
- Modify: `spec/UI.md`
- Generated: `web/asr_realtime/`

- [ ] Document the shared particle layer, reduced-motion behavior, and localized hero purpose.
- [ ] Rebuild fresh Docker test images and run `./run.sh --test` to `TESTS_OK`.
- [ ] Deploy without activating audio hardware and verify `/`, `/static/particle-field.js`, and `/asr_realtime` return HTTP 200.
- [ ] Capture and inspect desktop, pointer-interaction, reduced-motion, and narrow-viewport screenshots for layering and readability.
- [ ] Run `git diff --check`, commit only source/tests/spec/generated web assets, keep `.superpowers/` untracked, and push `main`.
