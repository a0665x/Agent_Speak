# Pointer-Activated Particle Energy Trail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make both particle backgrounds denser and larger while keeping them near black until pointer movement creates a visible four-second glow-and-repulsion trail, and relax both display headings so glyphs and lines do not overlap.

**Architecture:** Extend the dependency-free `web/particle-field.js` engine with pure energy injection, appearance, and elapsed-time decay functions. Runtime pointer events inject energy once per actual movement segment; the animation loop consumes that energy to control alpha, size, displacement, and spring return. The homepage and React ASR wrapper continue mounting the same asset with separate visual profiles.

**Tech Stack:** Canvas 2D, browser JavaScript, Node test runner, React 19, TypeScript, Vitest, Vite, FastAPI static assets, Docker Compose.

---

### Task 1: Lock the energy-trail and typography contracts

**Files:**
- Modify: `tests/particle_field.test.js`
- Modify: `tests/test_webui.py`

- [x] **Step 1: Add failing pure particle tests**

Add tests that require both profiles to exceed their former density budgets, require `injectTrailEnergy` to energize particles along a movement segment while leaving distant particles dormant, require `particleAppearance` to enlarge and brighten energized particles, and require `decayEnergy(1, 4000)` to reach approximately `0.02`.

```js
const { decayEnergy, injectTrailEnergy, particleAppearance } = require("../web/particle-field.js");

test("energizes a continuous pointer segment and leaves distant particles dormant", () => {
  const particles = [
    { baseX: 50, baseY: 50, x: 50, y: 50, vx: 0, vy: 0, depth: 1, energy: 0 },
    { baseX: 500, baseY: 500, x: 500, y: 500, vx: 0, vy: 0, depth: 1, energy: 0 },
  ];
  const next = injectTrailEnergy(particles, { x: 0, y: 50 }, { x: 100, y: 50 }, "hero");
  assert.ok(next[0].energy > 0.7);
  assert.equal(next[1].energy, 0);
});

test("active particles grow, brighten, and fade near dark after four seconds", () => {
  const dormant = particleAppearance({ depth: 1, energy: 0 }, "hero");
  const active = particleAppearance({ depth: 1, energy: 1 }, "hero");
  assert.ok(active.radius >= dormant.radius * 1.35);
  assert.ok(active.alpha > dormant.alpha * 20);
  assert.ok(Math.abs(decayEnergy(1, 4000) - 0.02) < 0.002);
});
```

- [x] **Step 2: Add failing CSS contract assertions**

Extend the web CSS route test to require homepage tracking `-.038em` and line height `.94`. Read the ASR stylesheet from the repository and require the same tracking with line height `.90` plus a non-darkening particle canvas opacity of at least `.9`.

```python
assert "letter-spacing: -.038em" in css
assert "line-height: .94" in css
asr_css = Path("frontend/realtime/src/styles.css").read_text(encoding="utf-8")
assert "line-height: .90" in asr_css
```

- [x] **Step 3: Run focused tests and confirm RED**

Run: `node --test tests/particle_field.test.js && pytest -q tests/test_webui.py`

Expected: FAIL because the energy helpers, cinematic budgets, four-second decay, and relaxed typography do not exist yet.

### Task 2: Implement movement-only energy, larger particles, and four-second decay

**Files:**
- Modify: `web/particle-field.js`
- Test: `tests/particle_field.test.js`

- [x] **Step 1: Replace permanently bright profiles with bounded cinematic profiles**

Define `hero` and `subtle` with approximately 18/20 px nominal spacing, bounded desktop budgets near 2,600/2,200, a shared 180 px influence radius, stronger pointer force, dormant and active opacity, `activeRadiusScale: 1.45`, `trailLifetimeMs: 4000`, and `trailFloor: 0.02`.

```js
hero: Object.freeze({ spacing: 18, maxParticles: 2600, dormantOpacity: 0.012, activeOpacity: 0.9, pointerRadius: 180, pointerForce: 2.4, activeRadiusScale: 1.45, trailLifetimeMs: 4000, trailFloor: 0.02, spring: 0.05, damping: 0.82 }),
subtle: Object.freeze({ spacing: 20, maxParticles: 2200, dormantOpacity: 0.008, activeOpacity: 0.76, pointerRadius: 180, pointerForce: 2.4, activeRadiusScale: 1.45, trailLifetimeMs: 4000, trailFloor: 0.02, spring: 0.05, damping: 0.82 }),
```

- [x] **Step 2: Implement pure energy and appearance helpers**

Export `decayEnergy(energy, elapsedMs, profileName)`, `injectTrailEnergy(particles, start, end, profileName)`, and `particleAppearance(particle, profileName)`. Interpolate movement samples no farther than 12 px apart, clamp energy to one, inject velocity away from samples, and calculate time-based decay with `Math.pow(profile.trailFloor, elapsedMs / profile.trailLifetimeMs)`.

- [x] **Step 3: Change runtime pointer handling to movement-only injection**

Track the previous pointer position. On a non-touch `pointermove`, ignore duplicate positions below a one-pixel threshold; otherwise inject the segment immediately and store the new position. Do not keep an active pointer that applies force every animation frame. Pointer exit and blur clear only the previous position, leaving existing energy to fade naturally.

- [x] **Step 4: Render energy-driven size and alpha**

Advance spring motion and decay with a clamped elapsed frame delta, then draw using `particleAppearance`. Remove the permanently visible radial canvas glow. Keep dormant particles barely visible and stop drawing energy below a small cutoff without changing deterministic layout.

- [x] **Step 5: Run focused particle tests until GREEN**

Run: `node --test tests/particle_field.test.js`

Expected: all particle tests pass, including the existing single-loop and Reduced Motion lifecycle tests.

### Task 3: Relax headings and expose the brighter ASR profile

**Files:**
- Modify: `web/app.css`
- Modify: `frontend/realtime/src/styles.css`
- Modify: `spec/UI.md`
- Test: `tests/test_webui.py`
- Test: `frontend/realtime/src/App.test.tsx`

- [x] **Step 1: Adjust homepage typography and canvas presentation**

Set homepage `h1` to `line-height: .94` and `letter-spacing: -.038em`. Keep `.particle-field` at full presentation opacity because dormant/active brightness now belongs to the engine profile rather than CSS.

- [x] **Step 2: Adjust ASR typography and second-layer brightness**

Set ASR `h1` to `line-height: .90` and `letter-spacing: -.038em`. Raise `.ambient-particles` from `.52` to `.92` so the subtle profile is visible while retaining its lower active alpha inside the engine.

- [x] **Step 3: Document the energy-driven interaction**

Update `spec/UI.md` to state that untouched particles remain near black, pointer movement creates a larger repelled trail, stationary pointers do not refresh energy, and the afterglow fades over approximately four seconds.

- [x] **Step 4: Run web and frontend tests and build**

Run: `pytest -q tests/test_webui.py`

Run: `npm test -- --run && npm run build` from `frontend/realtime/`.

Expected: web tests pass, 13 frontend test files pass, and Vite regenerates `web/asr_realtime/` successfully.

### Task 4: Verify, review, deploy, and publish

**Files:**
- Generated: `web/asr_realtime/`
- Modify: `spec/references/20260722-particle-energy-trail-plan.md` checkboxes only

- [x] **Step 1: Run full fresh container verification**

Run: `AGENT_SPEAK_ACCELERATOR=cpu docker compose -f compose.yaml build gateway-test frontend-test`

Run: `AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test`

Expected: backend suite passes, 13 frontend files / 57 tests pass or higher, and output ends with `TESTS_OK`.

- [x] **Step 2: Deploy without activating audio hardware**

Run: `AGENT_SPEAK_ACCELERATOR=auto ./run.sh --up`

Expected: `GATEWAY_READY` with homepage, ASR, and docs URLs. Do not invoke device-check, listening, capture, playback, or TTS actions.

- [x] **Step 3: Inspect live presentation**

Capture homepage and ASR desktop screenshots after no movement to verify the near-black dormant field, then use browser pointer movement to verify a visible large-particle trail, stationary fade, and spring return. Capture a narrow viewport and Reduced Motion frame to verify readable non-overlapping headings and static low-luminance particles.

- [x] **Step 4: Run final review and repository checks**

Run: `git diff --check`, inspect the complete diff for unbounded history, frame-rate-dependent decay, duplicate animation loops, inaccessible canvas behavior, and accidental `.superpowers/` staging.

- [x] **Step 5: Commit and push main**

Stage only source, tests, specs, and generated Vite assets. Commit with `feat: add pointer-activated particle trails`, push `main`, then verify `HEAD` equals `origin/main` and `.superpowers/` remains untracked.
