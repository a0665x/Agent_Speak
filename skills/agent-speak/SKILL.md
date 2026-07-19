---
name: agent-speak
description: 操作本機 Agent Speak 語音 gateway，透過 stdio MCP 檢查能力與音訊裝置，完成 listen、外部 Agent 推理、speak 的安全互動流程。
version: 1.0.0
license: MIT
metadata:
  tags: [voice, mcp, agent, asr, tts]
---

# Agent Speak 操作 Skill

本 Skill 是可攜式操作知識，不是程式執行環境。控制工具由本機 stdio MCP 提供；音訊資料與事件仍經 Agent Speak HTTP/WebSocket API。不得把即時 raw audio stream 塞入 MCP。

## 啟動前檢查

1. 在 repository 根目錄確認 Docker Engine、Compose v2 與 `/dev/snd` 是否存在。
2. 執行 `./run.sh --build`；此命令建置並啟動隔離的 Gateway，預設只發布到 `127.0.0.1:8765`。
3. Compose 預設將 host `/dev/snd` 映射進 container，模型與私有狀態分別持久化在 `models/`、`data/`、`runtime/`。
4. 執行 `./run.sh --status` 或 MCP `status`；閱讀 `capabilities`，不要把 development provider 說成正式智慧 Agent。
5. 呼叫 MCP `list_audio_devices`。只有 capture available 才能錄音；只有 playback available 才能承諾實體播放。

## 連接 MCP

讓支援 stdio MCP 的宿主以 repository 的絕對路徑執行 `scripts/run_mcp.sh`，並可設定 `AGENT_SPEAK_URL=http://127.0.0.1:8765`。設定欄位名稱依宿主而異；核心概念只有 command、args、env。不要臆造 Hermes、Codex、OpenClaw 的產品專屬欄位，應查該宿主目前文件。

MCP 工具：

- `status`：gateway health 與 provider capabilities。
- `capabilities`：目前 provider 與限制。
- `list_audio_devices`：有 timeout 的 ALSA capture/playback 探測。
- `microphone_smoke`：錄製後立即刪除的短 WAV，不送 ASR；每次必須傳 `user_confirmed=true`。
- `listen_once`：短暫錄音，再經 HTTP `/api/v1/audio/asr` 辨識；每次必須傳 `user_confirmed=true`。
- `speak`：經 HTTP 合成；`playback=false` 是安全預設。實體播放必須同時指定 `playback=true`、`user_confirmed=true`，且偵測到 playback device 才執行 `aplay`。

## 外部 Agent 互動迴圈

1. 先取得使用者同意，再用 `listen_once(duration_seconds=3, device="default", user_confirmed=true)`。
2. 檢查回傳文字；空白、錯誤或語意不確定時詢問使用者，不猜測。
3. 由目前外部 Agent 自己推理、查工具並形成回覆。不要呼叫 gateway 的 dev echo 當作真正推理。
4. 先顯示回覆文字。取得播放同意且裝置可用後，呼叫 `speak(text=回覆, playback=true, user_confirmed=true)`。
5. 只有 `played=true` 才能宣稱已從喇叭播放；`synthesized=true` 僅表示已產生 WAV。
6. 每輪重新處理錯誤；不得建立無限制錄音或無限播放迴圈。

需要完整 pipeline 事件時，外部程式可建立 session，透過 HTTP 上傳 bounded PCM WAV，並以 WebSocket 訂閱事件。MCP 只做低頻控制，不取代資料/事件平面。

## 安全限制

- 未經明確同意不得啟動麥克風或喇叭；避免錄到旁人與敏感資訊。
- 錄音限制 1–30 秒；裝置值只接受安全 ALSA 名稱，不得傳 shell 片段。
- 預設 localhost。服務沒有驗證與傳輸加密，不得直接暴露到不受信任 LAN 或公網。
- 不提交 `.env`、credentials、錄音、speaker features、SQLite、generated audio、traces、模型或 weights。
- 不用 speaker matching 作身分驗證，不因 ASR 或 Agent 輸出執行破壞性操作。
- 工具錯誤應原樣、清楚回報；不可把合成成功誤報為播放成功。
