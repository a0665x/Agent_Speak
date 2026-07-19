# Agent Speak

[English](README.md) | 繁體中文

Agent Speak 是 Docker-first 通用語音閘道，讓外部 AI Agent 取得耳朵與聲音，但不綁定單一 LLM。Hermes、Codex、OpenClaw、以 Ollama 建立的 Agent，以及其他支援 MCP 的宿主，都能使用同一套有界語音流程：

`麥克風 → VAD → Faster-Whisper ASR → 外部 Agent → Piper TTS → 喇叭`

Gateway 提供 REST、WebSocket events、雙語 WebUI、OpenAPI 與 stdio MCP 控制平面。內建 Agent 階段仍是透明的 development echo；真正推理應由連接的外部 Agent 負責。

## 快速啟動

需求：Linux、Docker Engine、Docker Compose v2、`/dev/snd`，以及第一次下載模型所需的網路。

```sh
git clone https://github.com/a0665x/Agent_Speak.git
cd Agent_Speak
./run.sh --build
```

WebUI：http://127.0.0.1:8765

OpenAPI：http://127.0.0.1:8765/docs

`./run.sh --build` 會建置並啟動隔離環境。Compose 預設映射 `/dev/snd`，私有狀態持久化於已排除版控的 `data/`、`runtime/`、`models/`。

## 單一操作入口

```text
./run.sh --build      建置並啟動
./run.sh --up         啟動
./run.sh --down       停止；保留資料與模型
./run.sh --down_up    重建執行狀態
./run.sh --restart    與 --down_up 相同
./run.sh --rebuild    不用快取重建並啟動
./run.sh --status     顯示容器、API 與音訊狀態
./run.sh --logs       顯示最新 Gateway logs
./run.sh --test       在 Docker 執行完整測試
./run.sh --help       顯示指令說明
```

選用設定可放在不追蹤的 `.env`；公開範例見 [.env.example](.env.example)。主機預設只發布到 `127.0.0.1`，不會直接暴露於公網。持久化目錄可用 `AGENT_SPEAK_DATA_PATH`、`AGENT_SPEAK_RUNTIME_PATH`、`AGENT_SPEAK_MODELS_PATH` 覆寫。

## 透過 MCP 連接外部 Agent

讓 stdio MCP 宿主執行 repository 內 `scripts/run_mcp.sh` 的絕對路徑：

```json
{
  "command": "/absolute/path/to/Agent_Speak/scripts/run_mcp.sh",
  "args": [],
  "env": {
    "AGENT_SPEAK_URL": "http://127.0.0.1:8765"
  }
}
```

該腳本會把 MCP process 接到正在執行的 Gateway container。可用工具：

- `status`、`capabilities`
- `list_audio_devices`
- `microphone_smoke`
- `listen_once`
- `speak`

安全互動流程：

1. 先查看狀態、能力與音訊裝置。
2. 取得使用者明確同意後呼叫 `listen_once`。
3. 外部 Agent 使用自己的 LLM、工具、記憶與 Skills 推理。
4. 先顯示文字回答。
5. 取得播放同意後呼叫 `speak`；只有 `played=true` 代表真的由喇叭播放。

可將可攜式 Skill 安裝到相容宿主，或要求 Agent 先讀 [AGENTS.md](AGENTS.md) 與 [skills/agent-speak/SKILL.md](skills/agent-speak/SKILL.md)。完整 MCP 架構與宿主契約見 [spec/SKILL_AND_MCP.md](spec/SKILL_AND_MCP.md)。

## 對外介面

- WebUI：雙語錄音、上傳、流程時間線、結果與說話者資料
- REST/OpenAPI：有界 PCM WAV 階段 API 與完整語音回合
- WebSocket：有序 Session events
- stdio MCP：低頻控制；即時 raw audio 不經 JSON-RPC 傳輸

繁中 OpenAPI 快速入門：[docs/OPENAPI_QUICKSTART_ZH_TW.md](docs/OPENAPI_QUICKSTART_ZH_TW.md)

## 硬體與安全

- Compose 預設把 `/dev/snd` 映射到 Gateway container，供 ALSA 錄音與播放。
- 麥克風與實體播放工具每次都需要使用者明確同意。
- 服務沒有公網驗證；請保留 loopback 預設，或放在可信任的私人 HTTPS 層後方。
- Speaker matching 只供便利識別，不是 authentication。
- 錄音、生成音訊、說話者特徵、資料庫、模型、credentials、私鑰、Agent 本機狀態與 cache 都不會進 Git 或 Docker build context。
- `./run.sh --test` 使用無網路、無正式資料掛載、無 `/dev/snd` 的獨立測試容器。

架構、Runtime、測試與目前專案狀態請從 [spec/PROJECT_MAP.md](spec/PROJECT_MAP.md) 開始。
