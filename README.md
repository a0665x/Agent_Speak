# Agent Speak

English | [繁體中文](README.zh-TW.md)

Agent Speak is a Docker-first voice gateway that gives an external AI agent ears and a voice without locking the runtime to one LLM. Hermes, Codex, OpenClaw, Ollama-based agents, and other MCP-capable hosts can use the same bounded voice pipeline:

`microphone → VAD → Faster-Whisper ASR → external agent → Piper TTS → speaker`

The gateway exposes REST, WebSocket events, a bilingual WebUI, OpenAPI documentation, and a stdio MCP control plane. The built-in Agent stage remains a transparent development echo; real reasoning belongs to the connected external agent.

## Quick start

Requirements: Linux, Docker Engine with Compose v2, `/dev/snd`, and network access for the first model download.

```sh
git clone https://github.com/a0665x/Agent_Speak.git
cd Agent_Speak
./run.sh --build
```

WebUI: http://127.0.0.1:8765

OpenAPI: http://127.0.0.1:8765/docs

Realtime Studio: http://127.0.0.1:8765/realtime

`/realtime` is continuous transcription only: it does not call the Agent stage, TTS, Codex injection, or speaker playback. The browser enables Start only after an explicit check can see both Zone Vibe 100 input and output endpoints; output visibility is not proof of physical playback. Raw PCM16 travels over the realtime WebSocket, while MCP remains a low-frequency control plane.

VAD produces rolling partial text, so the current words may change. Qwen correction may revise the previous sentence together with the current sentence; older sentences lock. A silence candidate starts at 900 ms and may extend to the 1,800 ms hard endpoint. Invalid, late, or excessive Qwen edits fall back to final ASR text. The client does not reconnect automatically. CPU mode is functional, while realtime latency and GPU gains depend on the host.

`./run.sh --build` builds and starts the isolated stack. Compose maps `/dev/snd` by default and persists private state in ignored `data/`, `runtime/`, and `models/` directories.

## Verify the installation

```sh
./run.sh --status
./scripts/health_smoke.sh
./scripts/smoke_api.sh
./run.sh --test
```

`--status` checks container health plus real ALSA capture/playback discovery. The two smoke scripts automatically run inside the active Gateway container, so a Docker installation does not need a host Python environment: `health_smoke.sh` verifies health and writable storage, while `smoke_api.sh` exercises session creation, WebSocket events, a complete ASR/TTS turn, WAV artifact retrieval, and the speaker-profile lifecycle. `--test` runs the full isolated suite without production data mounts, network access, or `/dev/snd`.

Expected success markers include `STATUS_HEALTHY`, `HEALTH_SMOKE_OK mode=docker`, `API_SMOKE_OK mode=docker`, and `TESTS_OK`.

## One operator command

```text
./run.sh --build      Build and start
./run.sh --up         Start
./run.sh --down       Stop; preserve data and models
./run.sh --down_up    Recreate the stack
./run.sh --restart    Same as --down_up
./run.sh --rebuild    No-cache rebuild and start
./run.sh --status     Container, API, and audio status
./run.sh --logs       Latest gateway logs
./run.sh --test       Full test suite in Docker
./run.sh --help       Command reference
```

Optional settings can be placed in an untracked `.env`; see [.env.example](.env.example). The default host publication is `127.0.0.1`, not a public interface. Persistent host paths can be changed with `AGENT_SPEAK_DATA_PATH`, `AGENT_SPEAK_RUNTIME_PATH`, and `AGENT_SPEAK_MODELS_PATH`.

`AGENT_SPEAK_ACCELERATOR=auto` is the default. It selects the separate NVIDIA image only when `nvidia-smi` and Docker's NVIDIA runtime are both ready; otherwise it prints the reason and starts the CPU image. Use `cpu` to force the portable CPU/INT8 path or `nvidia` to require CUDA and fail instead of falling back. NVIDIA mode requires the NVIDIA Container Toolkit and builds `agent-speak:gpu-local` with CUDA 12 and cuDNN 9. `./run.sh --status` reports both the selected Compose accelerator and the ASR provider's actual device.

## Connect an external Agent through MCP

Point a stdio MCP host at the repository's absolute script path:

```json
{
  "command": "/absolute/path/to/Agent_Speak/scripts/run_mcp.sh",
  "args": [],
  "env": {
    "AGENT_SPEAK_URL": "http://127.0.0.1:8765"
  }
}
```

The script attaches the MCP process to the running gateway container. Available tools:

- `status` and `capabilities`
- `list_audio_devices`
- `microphone_smoke`
- `listen_once`
- `speak`

The safe interaction loop is:

1. Inspect `status`, capabilities, and audio devices.
2. With explicit user consent, call `listen_once`.
3. Let the external agent reason and use its own tools, memory, and skills.
4. Show the answer as text.
5. With playback consent, call `speak`; only `played=true` proves physical playback.

Install the portable Skill in a compatible host or ask the agent to read [AGENTS.md](AGENTS.md) and [skills/agent-speak/SKILL.md](skills/agent-speak/SKILL.md). The MCP architecture and host contract are defined in [spec/SKILL_AND_MCP.md](spec/SKILL_AND_MCP.md).

## Interfaces

- WebUI: bilingual recording, upload, pipeline timeline, results, and speaker profiles
- REST/OpenAPI: bounded PCM WAV stages and complete turns
- WebSocket: ordered session events
- stdio MCP: low-frequency control; raw realtime audio does not travel through JSON-RPC

Traditional Chinese OpenAPI guide: [docs/OPENAPI_QUICKSTART_ZH_TW.md](docs/OPENAPI_QUICKSTART_ZH_TW.md)

## Hardware and security

- `/dev/snd` is mapped into the gateway container by default for ALSA capture and playback.
- NVIDIA acceleration is optional. Hosts without a supported NVIDIA Docker runtime continue on CPU in `auto` mode.
- Microphone and physical playback tools require explicit per-call user consent.
- The service has no public-network authentication. Keep the default loopback binding or place it behind a trusted private HTTPS layer.
- Speaker matching is convenience identification, not authentication.
- Recordings, generated audio, speaker features, databases, models, credentials, private keys, local Agent state, and caches are excluded from Git and Docker build context.
- `./run.sh --test` uses a separate no-network container without production mounts or `/dev/snd`.

Architecture, runtime, tests, and project state start at [spec/PROJECT_MAP.md](spec/PROJECT_MAP.md).
