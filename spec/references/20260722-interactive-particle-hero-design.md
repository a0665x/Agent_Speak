# Interactive particle hero and page messaging

## Intent

Give the project guide and ASR demo a spatial, responsive background inspired
by the visual depth of modern particle-field landing pages, without copying
third-party branding, assets, or an exact particle pattern. Reframe the product
around an Agent that can listen and naturally join a conversation, while making
the ASR page's purpose immediately clear.

## Localized messaging

The homepage hero communicates “Let your Agent listen freely and join the
conversation.” The ASR hero is titled “ASR Realtime Demo” and its supporting
copy promises fast access to model selection, processing state, and transcript
visualization. English remains the default; Traditional Chinese, Japanese, and
Korean receive equivalent natural-language copy, document titles, and metadata.

## Particle system

A single dependency-free Canvas 2D engine is served as a static browser asset
and mounted by both pages:

- deterministic point rows form a quiet three-dimensional wave field;
- depth changes dot radius, opacity, and cool ice/violet color;
- pointer proximity gently displaces dots and they spring back without jitter;
- the homepage uses the primary density and brightness;
- the ASR page uses a lower-density, lower-opacity profile so controls,
  transcripts, graphs, and audio visualization remain dominant;
- the canvas is fixed, decorative, `aria-hidden`, and `pointer-events: none`;
- pointer coordinates are observed at window level, so interaction never steals
  clicks, focus, scrolling, or audio controls;
- pixel ratio is capped, particle count is bounded, hidden tabs stop drawing,
  and resize work is debounced through the next animation frame.

When `prefers-reduced-motion: reduce` is active, the engine draws one static
frame without pointer response or a continuous animation loop. Narrow screens
use fewer particles and touch does not create persistent hover behavior.

## Layering

Existing oversized ambient words and gradients remain. The particle canvas
sits above the page background but behind navigation and content. The existing
homepage illustration remains as a foreground product visual. On the ASR page,
the prior line-wave background is replaced by the subtler particle field so two
continuous full-screen canvases do not compete for GPU time.

## Verification

Pure JavaScript tests cover deterministic layout, bounded density, pointer
displacement, spring return, and reduced-motion configuration. Web route tests
cover the static asset and both page hooks. React tests cover the subtle ASR
profile and four-language hero/document wording. Final verification includes
the complete Docker suite, production build, reduced-motion headless capture,
pointer-interaction capture, and live HTTP checks without microphone or speaker
activation.

