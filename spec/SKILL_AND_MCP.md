# Portable Skill and stdio MCP

## Purpose

Agent Speak gives arbitrary external Agents a common voice peripheral. The Gateway does not force Hermes, Codex, OpenClaw, Ollama-based agents, or other hosts to surrender their own LLM, memory, tools, Skills, or permissions.

## Three planes

1. Skill: `skills/agent-speak/SKILL.md` teaches an Agent how to inspect the runtime, request hardware consent, call tools, and handle errors.
2. stdio MCP: `agent_speak.mcp_server` provides status/capabilities, ALSA discovery, bounded microphone capture, listen-once, TTS, and opt-in playback as small JSON results.
3. HTTP/WebSocket: bounded WAV remains on REST and ordered session events remain on WebSocket. Realtime raw audio is not transported through MCP JSON-RPC.

## Docker-first startup

```sh
./run.sh --build
./run.sh --status
```

`compose.yaml` maps host `/dev/snd` into the Gateway container by default. The Agent must still call `list_audio_devices`; a mapped path does not prove a working capture or playback endpoint.

A stdio MCP host runs:

```sh
/absolute/path/to/Agent_Speak/scripts/run_mcp.sh
```

Host configuration concept:

```json
{
  "command": "/absolute/path/to/Agent_Speak/scripts/run_mcp.sh",
  "args": [],
  "env": {"AGENT_SPEAK_URL": "http://127.0.0.1:8765"}
}
```

`scripts/run_mcp.sh` uses `docker compose exec -T gateway` when the Docker stack is running. This preserves stdio framing while keeping dependencies in the container. Product-specific config file names and schemas must be taken from the current MCP host documentation.

## External Agent loop

`listen_once → Gateway ASR transcript → external Agent reasoning/tools → speak(text, playback?)`

The built-in `/api/v1/agent/respond` provider is a transparent development echo, not external-Agent reasoning. For a full session, clients may instead use `POST /sessions`, a bounded WAV turn, and WebSocket events.

## MCP tools

- `status()`: Gateway health and capabilities; unreachable state is explicit.
- `capabilities()`: active providers and limitations.
- `list_audio_devices()`: bounded `arecord -l` and `aplay -l` discovery.
- `microphone_smoke(duration_seconds, device, user_confirmed)`: consent-gated capture whose temporary WAV is removed.
- `listen_once(duration_seconds, device, user_confirmed)`: consent-gated capture followed by `/api/v1/audio/asr`.
- `speak(text, playback, device, user_confirmed)`: synthesize through HTTP; physical playback requires both `playback=true` and consent. Only successful `aplay` returns `played=true`.

## Hardware and consent contract

Container access to `/dev/snd` is necessary but not sufficient. Agents must:

1. Check capture/playback discovery.
2. Obtain explicit consent for each recording or physical playback call.
3. Never promise playback when only synthesis succeeded.
4. Report missing devices, timeout, ASR, TTS, and playback errors accurately.
5. Avoid unbounded listening or playback loops.

ALSA device names are validated; subprocesses do not use a shell. HTTP has timeout and response-size bounds. Speaker matching is convenience identification, not authentication.

## Private state

Recordings, generated audio, speaker features, databases, logs, traces, secrets, model weights, Agent-local state, `data/`, `runtime/`, and `models/` are excluded from Git and the Docker build context. The default host publication is loopback-only; remote access requires a trusted private HTTPS layer.
