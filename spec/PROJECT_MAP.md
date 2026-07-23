# Project Map

## Name
Agent Speak — Local Voice Agent Gateway

## Description
Docker-first, Jetson-oriented local voice pipeline with an English-default project guide, a device-gated `/asr_realtime` demo, localized portal/Swagger presentation in `en`, `zh-TW`, `ja`, and `ko`, session-frozen realtime speech policies for `auto`, `en`, `zh-TW`, `ja`, and `ko`, and stable VAD, ASR, correction, endpoint, external Agent, TTS, speaker-profile, MCP, REST, and WebSocket boundaries.

## Read first
- [Agent quick start](agent.md)
- [Repository map](map.md)
- [Current state](project_herness.md)
- [Architecture](ARCHITECTURE.md)
- [API](API.md)
- [OpenAPI 常用操作繁中快速入門](../docs/OPENAPI_QUICKSTART_ZH_TW.md)
- [Runtime](RUNTIME.md)
- [Testing](TESTING.md)
- [UI](UI.md)
- [Portable Skill and stdio MCP](SKILL_AND_MCP.md)
- [Session-frozen speech language routing](references/lesson-20260721-session-language-routing.md)
- [Multi-model realtime ASR and generic audio devices](references/20260722-multi-model-realtime-design.md)
- [Realtime model status synchronization](references/20260722-model-status-synchronization-design.md)
- [Realtime model reliability and diagnostic logging](references/20260722-realtime-model-reliability-and-logging-design.md)
- [Interactive particle hero and ASR ambience](references/20260722-interactive-particle-hero-design.md)
- [Pointer-activated particle energy trails](references/20260722-particle-energy-trail-design.md)
- [VoxCPM2 TTS clone test design](references/20260723-voxcpm2-tts-clone-test-design.md)
- [VoxCPM2 TTS clone test implementation plan](references/20260723-voxcpm2-tts-clone-test-plan.md)
- [Extensible GPU resource orchestrator design](references/20260723-resource-orchestrator-design.md)

## Change guide
Docker lifecycle, structured diagnostics, and image: `../run.sh`, `../Dockerfile`, `../compose.yaml`, RUNTIME.md, and references/20260722-realtime-model-reliability-and-logging-design.md. Extensible workload residency, reset/reconciliation controls, and future full-pipeline placement: references/20260723-resource-orchestrator-design.md. VoxCPM2, zero-shot clone privacy, and the current exclusive GPU mode: references/20260723-voxcpm2-tts-clone-test-design.md and its implementation plan. Pipeline/provider: ARCHITECTURE.md and API.md. Realtime speech-language routing: references/lesson-20260721-session-language-routing.md. Multi-model realtime ASR and device generalization: references/20260722-multi-model-realtime-design.md. Model selector/detail/lifecycle consistency: references/20260722-model-status-synchronization-design.md. Shared homepage/ASR particle behavior: references/20260722-interactive-particle-hero-design.md and references/20260722-particle-energy-trail-design.md. External Agent integration: SKILL_AND_MCP.md and `../skills/agent-speak/SKILL.md`. MCP implementation: `../src/agent_speak/mcp_server.py`; entry point: `../scripts/run_mcp.sh`; hardware-free regression: `../tests/test_mcp_server.py`. Project homepage, ASR, and TTS clone UI: UI.md, `../web`, and `../frontend/realtime`. Verification: TESTING.md. Model replacement: references/MODEL_STRATEGY.md.

## Safety
Voice data, embeddings, secrets, databases, weights, generated audio, and traces are private runtime artifacts and must not be committed.
