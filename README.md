# Agent Speak

Agent Speak 是 local-first Voice Agent gateway，主要面向 Jetson AGX Orin，也可在具備 Python 3.11 與相容音訊裝置的 Linux 使用。它提供 bounded WAV、VAD、Faster-Whisper ASR、文字處理、可替換 Agent provider、Piper TTS、REST/WebSocket API、WebUI，以及可供外部 Agent 使用的本機 stdio MCP 控制平面。

重要現況：gateway 內建 Agent 仍是透明的 development echo，不是真正 LLM。真正的 Hermes、Codex、OpenClaw 或其他外部 Agent 應採 `listen/transcribe → 自己推理 → speak`，不要把 dev echo 說成智慧回答。

## 從 clone 到啟動

需求：Linux、Python 3.11、可選的 ALSA `arecord`/`aplay`，以及第一次下載 speech models 所需的網路。Ubuntu/Jetson 若缺少系統工具，可先安裝 `python3.11-venv` 與 `alsa-utils`（套件名稱依發行版調整）。

```sh
git clone https://github.com/a0665x/Agent_Speak.git
cd Agent_Speak
./scripts/setup.sh
./scripts/run.sh
```

Setup 只建立並使用專案 `.venv`，不安裝到 global Python。需要覆寫設定時才執行 `cp .env.example .env`；`.env` 不得提交。

開啟 `http://127.0.0.1:8765`，API 文件位於 `http://127.0.0.1:8765/docs`。繁中 API 教學見 [docs/OPENAPI_QUICKSTART_ZH_TW.md](docs/OPENAPI_QUICKSTART_ZH_TW.md)。

另一個 terminal 可驗證：

```sh
./scripts/status.sh
./scripts/health_smoke.sh
./scripts/smoke_api.sh
./scripts/test.sh
```

## 檢查麥克風與喇叭

```sh
arecord -l
aplay -l
./scripts/mic_smoke.sh
```

`mic_smoke.sh` 是有界限的短錄音並會清除暫存檔。可用 `AGENT_SPEAK_MIC_DEVICE=plughw:1,0` 覆寫裝置。沒有喇叭時仍可合成 WAV，但不得宣稱已實體播放。

## 連接任意支援 stdio MCP 的 Agent

先保持 `./scripts/run.sh` 執行，再讓 MCP host 啟動：

```sh
./scripts/run_mcp.sh
```

通用 MCP 設定概念：

```json
{
  "command": "/absolute/path/to/repository/scripts/run_mcp.sh",
  "args": [],
  "env": {
    "AGENT_SPEAK_URL": "http://127.0.0.1:8765"
  }
}
```

請把 command 換成 clone 後的實際絕對路徑。Hermes、Codex、OpenClaw 若其目前版本支援 stdio MCP，都可使用相同 command/args/env 概念；各產品設定檔位置與 schema 可能變動，請以該產品最新文件為準。本專案不聲稱未實際驗證的產品專屬欄位。

MCP 工具包括 `status`、`capabilities`、`list_audio_devices`、`microphone_smoke`、`listen_once` 與 `speak`。MCP 是低頻控制平面；WAV 仍經既有 bounded HTTP API，session events 經 WebSocket，不會把即時 raw audio stream 塞進 MCP。

完整設計、安全語意與 host 範例見 [spec/SKILL_AND_MCP.md](spec/SKILL_AND_MCP.md)。可攜式 Agent 操作知識位於 [skills/agent-speak/SKILL.md](skills/agent-speak/SKILL.md)。Repository 根目錄的 [AGENTS.md](AGENTS.md) 會引導能讀取專案指令的 Agent 先進入這兩份文件；不支援自動發現的宿主，請直接要求它「先讀取 AGENTS.md 與 skills/agent-speak/SKILL.md，再設定 MCP」。

Hermes Agent 可直接安裝公開 Skill：

```sh
hermes skills install https://raw.githubusercontent.com/a0665x/Agent_Speak/main/skills/agent-speak/SKILL.md
```

Hermes 的 `~/.hermes/config.yaml` 可加入下列 stdio MCP 設定後重啟（替換絕對路徑）：

```yaml
mcp_servers:
  agent_speak:
    command: "/absolute/path/to/Agent_Speak/scripts/run_mcp.sh"
    args: []
    env:
      AGENT_SPEAK_URL: "http://127.0.0.1:8765"
```

可用 `hermes mcp list` 與 `hermes mcp test agent_speak` 檢查。其他 Agent 宿主請把相同 command/args/env 轉成其目前支援的 MCP 設定格式。

## 第一輪 listen → reasoning → speak

1. 外部 Agent 先呼叫 `status` 和 `list_audio_devices`。
2. 取得使用者錄音同意後，呼叫 `listen_once(duration_seconds=3, device="default", user_confirmed=true)`。
3. 外部 Agent 使用回傳 transcript 自己推理，先以文字顯示答案。
4. 使用者要求播放且 `playback.available=true` 時，呼叫 `speak(text="回答", playback=true, device="default", user_confirmed=true)`。
5. 只有結果 `played=true` 才代表喇叭確實成功播放；`synthesized=true` 只代表 gateway 已產生 WAV。

`speak` 預設 `playback=false`。錄音為 1–30 秒、ALSA device 有格式驗證、subprocess 不使用 shell 且有 timeout；暫存錄音與播放檔在結束時清除。

## Gateway 能力與邊界

- 接受 8–48 kHz、uncompressed 16-bit mono/stereo WAV，並限制 bytes 與 duration。
- 使用 energy VAD、local Faster-Whisper ASR 與 Piper TTS；模型 lazy load。
- 提供 VAD、ASR、correction、endpoint、Agent、TTS stage API 及完整 turn。
- REST 取得 session history，WebSocket 接收 bounded ordered events。
- WebUI 在瀏覽器將 MediaRecorder 結果轉為 PCM WAV 後才上傳。
- Speaker matching 只是 local convenience identification，not authentication，也不是安全控制。
- Correction、endpoint 和 Agent defaults 仍是 deterministic development providers；以 `/api/v1/capabilities` 為準。

## 網路與資料安全

服務預設只 bind `127.0.0.1`。MVP 沒有 authentication 或 transport encryption；不要直接暴露到不受信任 LAN 或 public internet。只有在 trusted network（受信任網路）與適當 host firewall 下，才考慮明確設定 `AGENT_SPEAK_HOST=0.0.0.0`。

`.gitignore` 排除 `.env`、agent/IDE state、caches、runtime/data、錄音、generated audio、databases、credentials、logs、traces、models 與 weights；保留可公開的 `.env.example`。提交前仍應執行 `git status --ignored` 與 secret scan，因 ignore 規則不能取代人工審查。

架構、API、操作與測試入口請從 [spec/PROJECT_MAP.md](spec/PROJECT_MAP.md) 開始。
