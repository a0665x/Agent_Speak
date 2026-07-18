# Project Map

## Name
Agent Speak — Local Voice Agent Gateway

## Description
Jetson-oriented local voice pipeline and WebUI exposing VAD, ASR, correction, endpoint detection, arbitrary agent, TTS, and speaker-profile boundaries through stable APIs.

## Read first
- [Agent quick start](agent.md)
- [Repository map](map.md)
- [Current state](project_herness.md)
- [Architecture](ARCHITECTURE.md)
- [API](API.md)
- [Runtime](RUNTIME.md)
- [Testing](TESTING.md)
- [UI](UI.md)

## Change guide
Pipeline/provider: ARCHITECTURE.md and API.md. UI: UI.md. Operations: RUNTIME.md and TESTING.md. Model replacement: references/MODEL_STRATEGY.md.

## Safety
Voice data, embeddings, secrets, databases, weights, generated audio, and traces are private runtime artifacts and must not be committed.
