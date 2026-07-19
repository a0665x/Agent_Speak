# Project Map

## Name
Agent Speak — Local Voice Agent Gateway

## Description
Docker-first, Jetson-oriented local voice pipeline and bilingual WebUI exposing VAD, ASR, correction, endpoint detection, arbitrary external Agent, TTS, speaker-profile, MCP, REST, and WebSocket boundaries through stable APIs.

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
Docker lifecycle and image: `../run.sh`, `../Dockerfile`, `../compose.yaml`, and RUNTIME.md. Pipeline/provider: ARCHITECTURE.md and API.md. External Agent integration: SKILL_AND_MCP.md and `../skills/agent-speak/SKILL.md`. MCP implementation: `../src/agent_speak/mcp_server.py`; entry point: `../scripts/run_mcp.sh`; hardware-free regression: `../tests/test_mcp_server.py`. UI: UI.md. Verification: TESTING.md. Model replacement: references/MODEL_STRATEGY.md.

## Safety
Voice data, embeddings, secrets, databases, weights, generated audio, and traces are private runtime artifacts and must not be committed.
