# Skill 與 MCP 整合

## 三個平面

Agent Speak 對外分成三個互補邊界：

1. Skill 是操作知識：`skills/agent-speak/SKILL.md` 告訴任意夠聰明的 Agent 如何檢查環境、取得同意、選擇工具與處理失敗。Skill 本身不開裝置、不承載權限。
2. stdio MCP 是控制平面：`agent_speak.mcp_server` 提供 health/capabilities、ALSA 裝置探測、bounded microphone capture、listen once 與 TTS/playback。它回傳小型 JSON 結果。
3. HTTP/WebSocket 是資料與事件平面：WAV 維持既有 bounded HTTP contract；session events 維持 WebSocket。即時 raw stream 不經 MCP，以免 JSON-RPC 記憶體膨脹、base64 overhead 與取消語意不清。

## 外部 Agent loop

推薦流程為：

`listen_once → gateway ASR/transcript → 外部 Agent 自己推理 → speak(text, playback?)`

Gateway 內建 Agent provider 目前仍是透明的 development echo，只用於既有完整 pipeline 開發與契約驗證。它不等同 Hermes、Codex、OpenClaw 或其他外部 Agent 的推理。外部 Agent 不應把 `/api/v1/agent/respond` 的 dev echo 當作自己的 reasoning。

需要完整 session 時，外部 Agent 可直接使用既有 HTTP `POST /sessions`、bounded WAV turn 與 WebSocket events；此變更沒有修改任何 `/api/v1` 契約。

## stdio 啟動與宿主設定

先啟動 gateway：

```sh
./scripts/setup.sh
./scripts/run.sh
```

再由 MCP host 以 stdio 啟動：

```sh
AGENT_SPEAK_URL=http://127.0.0.1:8765 ./scripts/run_mcp.sh
```

通用設定概念如下；請依 MCP host 的最新文件轉換欄位名稱：

```json
{
  "command": "/absolute/path/to/repository/scripts/run_mcp.sh",
  "args": [],
  "env": {"AGENT_SPEAK_URL": "http://127.0.0.1:8765"}
}
```

Hermes、Codex、OpenClaw 若其目前版本支援 stdio MCP，都可採相同 command/args/env 模式。repository 不聲稱任何未在本專案驗證的產品專屬設定檔名稱或 schema。

## MCP tools

- `status()`：合併 gateway health 與 capabilities；不可連線時明確回傳 `reachable=false`。
- `capabilities()`：讀取 `/api/v1/capabilities`。
- `list_audio_devices()`：分別執行 `arecord -l` 與 `aplay -l`，timeout 5 秒，不使用 shell。
- `microphone_smoke(duration_seconds, device, user_confirmed)`：1–30 秒 bounded capture；必須在該次工具呼叫傳入明確同意，暫存檔一定清除。
- `listen_once(duration_seconds, device, user_confirmed)`：明確同意後錄製 PCM WAV，再傳既有 `/api/v1/audio/asr`。
- `speak(text, playback, device, user_confirmed)`：呼叫既有 `/api/v1/tts/synthesize`。播放預設 false；要求播放時必須在該次呼叫傳入明確同意，並先確認 playback device、下載及驗證 bounded PCM WAV，再以 `aplay` 播放。只有成功 return code 才回 `played=true`。

裝置名稱只允許 ALSA 常見安全格式；subprocess 使用 argv、不用 shell，所有裝置命令都有 timeout。HTTP 有 timeout、response size 上限與可讀錯誤。

## 安全與隱私

麥克風、喇叭都需要使用者知情同意。MCP server 僅應連到可信 gateway；預設 localhost。MVP 無 authentication/TLS，不可直接公開。錄音、產生音訊、speaker 資料、資料庫、logs、traces、secrets 與模型 weights 全是 ignored local artifacts。`synthesized=true` 不代表實體播放；沒有 speaker 或播放失敗必須回 `played=false` 與錯誤。
