# Multilingual UI, OpenAPI, and README Visual Tour Design

**Date:** 2026-07-21
**Status:** Approved for implementation planning

## Goal

Make English the default presentation language across the Agent Speak project portal, ASR Realtime studio, and Swagger documentation. Add explicit Traditional Chinese, Japanese, and Korean switching from a consistent top-right control, while preserving every existing `/api/v1` runtime contract. Refresh the English-first README with real screenshots of each UI layer, an animated image carousel, and a static PNG gallery.

## Scope

The implementation covers:

- the project portal at `/`;
- the ASR Realtime application at `/asr_realtime`;
- Swagger UI at `/docs`;
- localized OpenAPI metadata returned by `/openapi.json?lang=...`;
- English, Traditional Chinese, Japanese, and Korean display copy;
- an English-first README visual tour;
- real English screenshots captured from the running local application;
- one animated carousel asset plus the original PNG screenshots.

It does not change API request or response payloads, provider behavior, audio processing, MCP tools, session behavior, authentication, or runtime error-envelope semantics. Screenshot capture must not request microphone permission, start a realtime session, invoke TTS, or play audio.

## Locale Contract

Supported locale identifiers are:

| UI label | Locale identifier |
| --- | --- |
| English | `en` |
| 繁體中文 | `zh-TW` |
| 日本語 | `ja` |
| 한국어 | `ko` |

English is always the default. The application does not select a language from browser preferences. Locale resolution uses this order:

1. a supported `lang` query parameter;
2. a supported value saved in `localStorage`;
3. `en`.

An unsupported or malformed locale falls back safely to English. Changing the selector updates the current surface, saves the locale, updates the document `lang`, and preserves the locale in navigation between `/`, `/asr_realtime`, and `/docs`.

## Shared User Experience

Every primary surface displays the same compact language selector in the top-right navigation area. The control must be keyboard accessible, expose a localized accessible name, retain visible focus, and avoid layout shifts when translated labels differ in length.

Technical identifiers remain stable and generally untranslated: Agent Speak, API paths, JSON property names, model/provider names, VAD, ASR, TTS, PCM, WAV, WebSocket, session IDs, device names, and timing values. Human explanations around those identifiers are localized.

The existing Apple-inspired visual system, motion, interaction feedback, responsive behavior, and reduced-motion support remain intact.

## Project Portal

The portal uses one structured locale catalog for all visible and assistive copy, including:

- metadata and page title;
- skip link and navigation labels;
- hero eyebrow, heading, body, action, image alternative text, and caption;
- API Explorer, ASR Realtime, and System Status cards;
- loading, ready, unavailable, and provider status wording;
- pipeline preview labels and explanations;
- footer safety statement.

The portal continues to perform only the existing health and capabilities reads. It must never request microphone access or start audio behavior.

## ASR Realtime

The React application uses a typed locale catalog and locale context. All presentation components receive translated human copy without changing the realtime reducer, WebSocket event types, audio framing, endpoint rules, or graph data model.

Localization includes:

- navigation, headings, explanatory copy, and session state;
- device-check state, buttons, readiness details, and permission guidance;
- start/stop listening controls;
- process-cycle stage names and descriptions;
- audio activity and inference-worker labels;
- queue and endpoint explanations;
- partial, endpoint, corrected, and final transcript labels;
- utterance graph title, legend, empty state, node tooltip labels, and assistive text;
- client-side errors, warnings, and live-region announcements.

Provider-supplied model names, API error text, transcript content, and spoken language are displayed as received. The UI may localize its surrounding error guidance, but it must not mutate server error payloads.

## Localized OpenAPI Architecture

The application keeps one canonical OpenAPI structure and applies a locale-specific metadata overlay. This avoids four independently maintained API contracts.

The default `/openapi.json` response is English. A supported `lang` query selects a localized representation:

- `/openapi.json?lang=en`
- `/openapi.json?lang=zh-TW`
- `/openapi.json?lang=ja`
- `/openapi.json?lang=ko`

Each representation has identical paths, methods, operation IDs, component names, property names, types, required fields, defaults, numeric constraints, status codes, and content types. Only human-facing metadata changes:

- API title and description where applicable;
- tag names and descriptions;
- endpoint summaries and descriptions;
- query parameter, request body, and binary WAV descriptions;
- response model and field descriptions;
- human-language example text.

The locale layer uses stable semantic keys rather than editing Swagger-rendered DOM nodes. Tests compare schemas after stripping translatable metadata to ensure structural equality.

Swagger UI at `/docs` reads the same locale contract, displays the shared top-right language selector, and loads the matching localized OpenAPI URL. Switching languages reloads Swagger with the selected schema and persists the choice. Direct `/docs?lang=...` links remain shareable.

## Translation Organization

Translation catalogs live close to their consumers while sharing the same locale identifiers and fallback rules:

- a small browser locale utility and catalog for the build-free portal;
- a typed TypeScript catalog/context for ASR Realtime;
- Python OpenAPI metadata catalogs and deterministic overlay functions for Swagger schemas.

Catalog completeness tests require every non-English locale to contain the canonical English keys. Missing runtime keys fall back to English instead of rendering blank text or raw key identifiers.

Translations should be natural product copy rather than literal word-for-word conversion. English is the canonical authoring language for new UI and API documentation.

## README and Visual Assets

`README.md` remains the primary English entry point and links to the existing Traditional Chinese README. The refreshed top section explains the three product surfaces, links to their canonical routes, and presents an English visual tour.

GitHub README pages do not execute an application-owned JavaScript carousel, so the repository uses two complementary formats:

1. an animated GIF that cycles through the English screenshots;
2. a static, clickable PNG gallery with a concise English caption for every layer.

The PNG source images are retained under `docs/screenshots/`. Planned layers are:

1. project portal hero and navigation;
2. portal destinations and live system status;
3. portal local processing path;
4. ASR Realtime hero, device gate, and listening controls;
5. realtime process cycle and active-model presentation;
6. transcript presentation;
7. utterance embedding graph and node interaction area;
8. localized Swagger API Explorer.

Screenshots use `?lang=en`, a consistent desktop viewport, and the real running application. They may show safe idle/readiness presentation produced by normal read-only status requests. They must not fabricate a successful microphone capture or activate microphone/speaker hardware. The animated asset is optimized for repository size and legibility; the original PNGs remain available for detailed viewing.

## Testing Strategy

Implementation follows test-driven development. Automated coverage includes:

- locale resolution, persistence, fallback, and query-link propagation;
- complete locale-key coverage for all four languages;
- portal English default and four-language rendering hooks;
- React language switching and translated component copy;
- unchanged realtime state and audio client behavior;
- localized Swagger selector and schema URL;
- four localized OpenAPI documents;
- structural equality of all localized schemas;
- translated endpoint, request, response, and model-field metadata;
- unknown-locale fallback to English;
- unchanged `/api/v1` behavior and existing contract tests.

Final verification also includes the full project test command, live route checks, desktop screenshot inspection, README link/asset checks, Git diff hygiene, and confirmation that no private runtime/audio/model data is staged.

## Delivery and Git Scope

The implementation is committed to the existing `main` branch as explicitly requested. The final push to `origin/main` will include the branch's existing unpublished commits together with the new localization, documentation, and screenshot commits. `.superpowers/`, `.env`, credentials, recordings, voice features, databases, runtime data, model weights, logs, and Agent-private state remain untracked and excluded.
