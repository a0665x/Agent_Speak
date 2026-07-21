# Project Map

## Name
Agent Speak — Local Voice Agent Gateway

## Description
Docker-first, Jetson-oriented local voice pipeline with an English-default project guide, a device-gated `/asr_realtime` demo, localized portal/Swagger presentation in `en`, `zh-TW`, `ja`, and `ko`, and stable VAD, ASR, correction, endpoint, external Agent, TTS, speaker-profile, MCP, REST, and WebSocket boundaries.

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

## Change guide
Docker lifecycle and image: `../run.sh`, `../Dockerfile`, `../compose.yaml`, and RUNTIME.md. Pipeline/provider: ARCHITECTURE.md and API.md. External Agent integration: SKILL_AND_MCP.md and `../skills/agent-speak/SKILL.md`. MCP implementation: `../src/agent_speak/mcp_server.py`; entry point: `../scripts/run_mcp.sh`; hardware-free regression: `../tests/test_mcp_server.py`. Project homepage and realtime UI: UI.md, `../web`, and `../frontend/realtime`. Verification: TESTING.md. Model replacement: references/MODEL_STRATEGY.md.

## Safety
Voice data, embeddings, secrets, databases, weights, generated audio, and traces are private runtime artifacts and must not be committed.
