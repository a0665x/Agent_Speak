# Agent Speak

[English](README.md) | 繁體中文

Agent Speak 是 Docker-first 通用語音閘道，讓外部 AI Agent 取得耳朵與聲音，但不綁定單一 LLM。Hermes、Codex、OpenClaw、以 Ollama 建立的 Agent，以及其他支援 MCP 的宿主，都能使用同一套有界語音流程：

`麥克風 → VAD → 可切換本機 ASR → 外部 Agent → Piper TTS → 喇叭`

Gateway 提供 REST、WebSocket events、英／繁中／日／韓 WebUI、完整多語 OpenAPI 與 stdio MCP 控制平面。介面預設英文，右上角可切換語言，選擇會跨首頁、Realtime Studio 與 Swagger 延續。內建 Agent 階段仍是透明的 development echo；真正推理應由連接的外部 Agent 負責。

## 快速啟動

需求：Linux、Docker Engine、Docker Compose v2、`/dev/snd`，以及第一次下載模型所需的網路。

```sh
git clone https://github.com/a0665x/Agent_Speak.git
cd Agent_Speak
./run.sh --models
./run.sh --build
```

WebUI：http://127.0.0.1:8765

OpenAPI：http://127.0.0.1:8765/docs?lang=zh-TW

Realtime Studio：http://127.0.0.1:8765/asr_realtime?lang=zh-TW

TTS Clone Test：http://127.0.0.1:8765/tts_clone_test?lang=zh-TW

`/asr_realtime` 只做持續轉錄，不呼叫 Agent、TTS、Codex session injection 或喇叭播放；舊 `/realtime` 會相容轉址到新路徑。瀏覽器必須先取得明確操作並同時看見目前系統預設的輸入與輸出端點（找不到 `default` 時退回第一個有標籤的裝置），才會開放開始按鈕；看見 output 不代表已完成 physical playback。Raw PCM16 走 realtime WebSocket，MCP 維持低頻控制平面。

Realtime Studio 的**語音語言**、**ASR 模型**與**校正模型**互相獨立。ASR 可選預設的 Qwen3-ASR 1.7B、Breeze-ASR-25 或 Faster Whisper Small；校正可選 Qwen2.5 Correction 或 Disabled / Raw ASR。下拉選單不需要 Submit：若正在聆聽，UI 會先安全停止、切換唯一常駐的 ASR 模型、建立選項已固定的新 session，並只在裝置閘門仍 Ready 時恢復。已完成的 transcript 與 graph 會保留，未完成 partial 會丟棄。

VAD 期間會持續產生 partial 文字，因此當前文字可能更新。Qwen 校正只可一起修訂 previous sentence（前一句）與當前句，更早的句子會鎖定。靜音 900 ms 形成候選句尾，必要時延長到 1,800 ms hard endpoint；Qwen timeout、格式錯誤或改寫過度時保留 final ASR。前端不會自動重連。CPU 模式可用，但 realtime latency 與 GPU 效益依主機而異。

`./run.sh --models` 會在保留至少 8 GiB 空間的前提下，明確且可重複地下載所有固定 revision 的推論檔案。下載採 atomic partial 目錄、驗證必要檔案、排除訓練 checkpoint，既有完整 cache 不會重抓。VoxCPM2 會在既有 ASR／校正／語音檔案之外增加約 9.6 GB，還需預留暫存下載與 image layer 空間；一般 `--build` 與 `--up` 只驗證模型，不會自行開始數 GB 下載。Compose 預設映射 `/dev/snd`，私有狀態持久化於已排除版控的 `data/`、`runtime/`、`models/`。

`/tts_clone_test` 有可自由切換的「語音克隆」與「TTS 播放」兩種模式。它只使用一段 5–30 秒、瀏覽器記憶體內的 zero-shot 參考，不是 LoRA 訓練。友善的語氣按鈕會轉成 best-effort 自然語言提示。瀏覽器只持有一份參考 Blob 與一份生成 Blob，替換或離頁即 revoke；Gateway 直接串流 WAV，不建立 artifact。只有按下「檢查裝置」才存取裝置、按下「開始錄音」才錄音、按下「播放」才會實體播放。

目前 11 GB 級目標需要使用互斥的 NVIDIA TTS mode。`./run.sh --tts-up` 會先停掉 ASR／校正 workers 再載入 VoxCPM2；`./run.sh --asr-up` 會停掉 VoxCPM2 並恢復即時轉錄。只有 CPU 的主機可查看頁面與復原提示，但無法執行此 TTS 功能。

## 驗證安裝

```sh
./run.sh --status
./scripts/health_smoke.sh
./scripts/smoke_api.sh
./run.sh --test
```

`--status` 會檢查容器健康狀態，並實際探測 ALSA 錄音與播放裝置。兩支 smoke 腳本會自動在執行中的 Gateway container 內運行，因此 Docker 安裝不需要主機 Python 環境：`health_smoke.sh` 驗證健康狀態與儲存空間可寫，`smoke_api.sh` 驗證 Session、WebSocket events、完整 ASR/TTS 回合、WAV 成品下載與說話者資料生命週期。`--test` 則在沒有正式資料掛載、網路及 `/dev/snd` 的隔離環境執行完整測試。

成功時應看到 `STATUS_HEALTHY`、`HEALTH_SMOKE_OK mode=docker`、`API_SMOKE_OK mode=docker` 與 `TESTS_OK`。

## 單一操作入口

```text
./run.sh --build      建置並啟動
./run.sh --up         啟動 ASR mode（等同 --asr-up）
./run.sh --asr-up     停止 VoxCPM2；啟動 ASR／校正與 Gateway
./run.sh --tts-up     停止 ASR／校正；啟動 VoxCPM2 與 Gateway（NVIDIA）
./run.sh --down       停止；保留資料與模型
./run.sh --down_up    重建執行狀態
./run.sh --restart    與 --down_up 相同
./run.sh --rebuild    不用快取重建並啟動
./run.sh --models     下載並驗證所有固定版本推論模型
./run.sh --status     顯示容器、API 與音訊狀態
./run.sh --logs       顯示最新 Gateway、ASR、校正與 TTS worker logs
./run.sh --logs asr-worker
                      只顯示最新 ASR worker logs
./run.sh --logs tts-worker
                      只顯示私有 vLLM-Omni worker logs
./run.sh --test       在 Docker 執行完整測試
./run.sh --help       顯示指令說明
```

選用設定可放在不追蹤的 `.env`；公開範例見 [.env.example](.env.example)。主機預設只發布到 `127.0.0.1`，不會直接暴露於公網。持久化目錄可用 `AGENT_SPEAK_DATA_PATH`、`AGENT_SPEAK_RUNTIME_PATH`、`AGENT_SPEAK_MODELS_PATH` 覆寫。

故障排除時先執行 `./run.sh --status`；辨識或模型錯誤查看 `./run.sh --logs asr-worker`，API／realtime 錯誤查看 `./run.sh --logs gateway`。系統也會在 `runtime/logs/` 與 `runtime/asr-worker/logs/` 寫入可輪替的 JSON Lines 診斷紀錄。`INFO` 記錄生命週期、`WARNING` 記錄可恢復錯誤與 retry、`ERROR` 記錄模型啟用或服務錯誤，選用的 `DEBUG` 會增加耗時與 queue 資訊。Log 可含 correlation ID、匿名 session、stage、model、device、latency 與錯誤類型，但不得包含音訊、辨識文字、裝置名稱、credentials、request body 或原始 session ID。可在 `.env` 設定 `AGENT_SPEAK_LOG_LEVEL`、`AGENT_SPEAK_LOG_MAX_BYTES` 與 `AGENT_SPEAK_LOG_BACKUP_COUNT`。

`AGENT_SPEAK_ACCELERATOR=auto` 是預設值。只有在 `nvidia-smi` 與 Docker NVIDIA runtime 都可用時才選擇獨立 NVIDIA 映像；否則會顯示原因並啟動 CPU 映像。`cpu` 會強制使用可攜式 CPU/INT8 路徑；`nvidia` 則要求 CUDA，無法使用時直接失敗而不降級。NVIDIA 模式需要 NVIDIA Container Toolkit，並建置含 CUDA 12 與 cuDNN 9 的 `agent-speak:gpu-local`。`./run.sh --status` 會同時顯示 Compose 選擇的 accelerator 與 ASR Provider 實際使用的 device。

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

- WebUI：英／繁中／日／韓錄音、上傳、流程時間線、結果與說話者資料
- REST/OpenAPI：有界 PCM WAV 階段 API、完整語音回合，以及四語 endpoint／參數／回應欄位說明
- WebSocket：有序 Session events
- stdio MCP：低頻控制；即時 raw audio 不經 JSON-RPC 傳輸

繁中 OpenAPI 快速入門：[docs/OPENAPI_QUICKSTART_ZH_TW.md](docs/OPENAPI_QUICKSTART_ZH_TW.md)

## 硬體與安全

- Compose 預設把 `/dev/snd` 映射到 Gateway container，供 ALSA 錄音與播放。
- NVIDIA 加速是選用功能；沒有受支援 NVIDIA Docker runtime 的主機在 `auto` 模式會繼續使用 CPU。
- 麥克風與實體播放工具每次都需要使用者明確同意。
- 服務沒有公網驗證；請保留 loopback 預設，或放在可信任的私人 HTTPS 層後方。
- Speaker matching 只供便利識別，不是 authentication。
- 錄音、生成音訊、說話者特徵、資料庫、模型、credentials、私鑰、Agent 本機狀態與 cache 都不會進 Git 或 Docker build context。
- `./run.sh --test` 使用無網路、無正式資料掛載、無 `/dev/snd` 的獨立測試容器。

架構、Runtime、測試與目前專案狀態請從 [spec/PROJECT_MAP.md](spec/PROJECT_MAP.md) 開始。
