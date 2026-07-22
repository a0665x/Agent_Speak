# Pointer-activated particle energy trails

## Intent

Refine the shared homepage and ASR particle field so it behaves like a dormant
dark surface that wakes under pointer movement. The result should use the
previously selected cinematic density, visibly displace larger particles along
the pointer path, retain a soft four-second afterglow, and then return to near
black. The homepage and `/asr_realtime` share the interaction model. ASR keeps
slightly lower peak brightness so pipeline state and transcript content remain
dominant.

The homepage and ASR display headings also receive more breathing room. Their
current tightly negative tracking and short line height must no longer make
glyphs or adjacent lines appear to overlap.

## Interaction model

Each deterministic particle owns a normalized `energy` value between zero and
one. Pointer position alone does not add energy. Energy is injected only when a
non-touch pointer moves far enough to produce a new path segment:

- interpolate long pointer segments at roughly 10–14 px intervals so fast
  movement produces a continuous trail rather than isolated bright circles;
- inject more energy near each sample and progressively less toward the edge of
  a 170–190 px influence radius;
- use that same local influence to repel particles, with approximately 2.3
  times the current peak force;
- let spring and damping return displaced particles without snapping or jitter;
- increase active particle radius by approximately 35–50 percent over the
  current visual size;
- drive alpha, radius, and a restrained cool glow from energy rather than from
  a permanently bright global field.

When the pointer stops, the last position is not continuously sampled and no
new energy is injected. Existing energy decays according to elapsed time, not
frame count, reaching a near-dark threshold after approximately four seconds.
This keeps the visible duration consistent on 60 Hz, high-refresh, and
temporarily delayed frames. Pointer exit clears path interpolation state but
does not abruptly erase the existing afterglow.

## Visual profiles

Both profiles use the selected cinematic density. The exact bounded particle
budgets may be tuned during screenshot verification, but the following
relationships are contractual:

- `hero` is substantially denser than the current 25 px / 1,400-particle
  profile and may reach roughly 2,400 visible particles on a desktop viewport;
- `subtle` is substantially denser than the current 36 px / 720-particle
  profile and stays close enough to `hero` that the second page no longer looks
  empty;
- dormant particles are only faintly visible, preserving spatial texture while
  leaving the page close to black before interaction;
- `hero` may reach roughly 85–90 percent active opacity;
- `subtle` uses the same radius, displacement, and decay behavior but a modestly
  lower active opacity so ASR controls remain legible;
- the existing full-canvas radial glow becomes energy-sensitive or is reduced
  enough that it cannot make an untouched page appear permanently illuminated.

The Canvas remains fixed, decorative, `aria-hidden`, and `pointer-events: none`.
Window-level pointer observation must never intercept clicks, focus, scrolling,
device checks, or listening controls.

## Typography

The homepage and ASR display headings retain the existing system typeface and
ice/violet treatment while moving from `-.075em` tracking to approximately
`-.038em`. Homepage line height targets approximately `.94`; ASR targets
approximately `.90`. Responsive rules may reduce type size or further relax
tracking where needed, but must not introduce horizontal scrolling, clipped
glyphs, or overlapping lines in any supported locale.

## Accessibility and performance

`prefers-reduced-motion: reduce` renders a static, low-luminance particle field
without pointer energy, displacement, floating motion, or an animation loop.
Touch movement does not activate a hover trail. Pixel ratio remains capped,
particle counts remain bounded, resize work stays animation-frame debounced,
and hidden documents pause rendering.

The animation uses one full-screen loop per page. Energy decay is based on the
measured frame delta and is clamped after long background gaps. Work per frame
must remain linear in the bounded particle count; no unbounded trail history or
recording is retained.

## Verification

Pure JavaScript tests cover cinematic density, larger active particles,
movement-only injection, interpolated path activation, visible repulsion,
elapsed-time four-second decay, spring return, and Reduced Motion. Existing web
and React tests continue to verify the shared asset and two page profiles.
Typography assertions lock the relaxed tracking and line height. Final
verification includes the complete Docker suite, production frontend build,
live HTTP checks, and desktop/ASR/narrow/Reduced Motion screenshots without
activating microphone or speaker hardware.
