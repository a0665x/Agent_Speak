# Agent Quick Start

1. Read PROJECT_MAP.md and project_herness.md.
2. Run `./scripts/status.sh` and `./scripts/test.sh` before behavior changes.
3. Source: `src/agent_speak`; UI: `web`; behavior tests: `tests`.
4. Preserve `/api/v1` contracts/provider boundaries. Add a failing test first.
5. Never commit `.env`, voice samples/features, databases, weights, generated audio, or traces.
6. Update the relevant Level-2 spec. UI work also requires API and browser smoke.
7. External Agent work starts with `SKILL_AND_MCP.md`: preserve Skill=knowledge, MCP=control, HTTP/WebSocket=data/events, and never route raw streams through MCP.
