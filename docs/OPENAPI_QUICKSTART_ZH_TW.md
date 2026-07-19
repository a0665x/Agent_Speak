# OpenAPI 常用操作繁中快速入門

這份文件帶你用 Agent Speak 的 Swagger UI 或 `curl` 完成最常用的操作。第一次使用建議先做「健康檢查」，再走一次「建立工作階段 → 上傳 WAV → 取得回覆」完整流程。

## 1. 先選擇連線網址

手機透過同一個 Tailnet 測試：

- WebUI：<https://ubuntu.tail9e662c.ts.net:8765/>
- Swagger UI：<https://ubuntu.tail9e662c.ts.net:8765/docs>
- OpenAPI JSON：<https://ubuntu.tail9e662c.ts.net:8765/openapi.json>

在專案主機本機測試：

- WebUI：<http://127.0.0.1:8765/>
- Swagger UI：<http://127.0.0.1:8765/docs>

以下指令預設使用 Tailscale HTTPS。若在主機本機執行，可把第一行改成 `http://127.0.0.1:8765`。

```sh
BASE_URL="https://ubuntu.tail9e662c.ts.net:8765"
```

目前 API 沒有登入驗證，只能透過受信任的本機或私人 Tailnet 使用。不要將服務直接公開到網際網路。

## 2. Swagger UI 怎麼操作

Swagger UI 適合第一次認識 API，不必先寫程式。

1. 開啟 <https://ubuntu.tail9e662c.ts.net:8765/docs>。
2. 展開一個操作，例如「系統 → GET /api/v1/health」。
3. 按右側的「Try it out」。
4. 填入參數或選擇 WAV 檔案。
5. 按「Execute」。
6. 查看下方資訊：
   - Request URL：實際呼叫的網址。
   - Curl：可複製到終端機重跑的指令。
   - Response code：HTTP 狀態碼，`200` 或 `201` 通常代表成功。
   - Response body：API 回傳的 JSON。

如果操作需要 `session_id` 或 `speaker_id`，先執行建立操作，再把回傳 JSON 裡的 `id` 複製到下一個操作。

## 3. 五分鐘完成第一個語音對話

### 步驟 1：確認服務正常

Swagger 操作：`GET /api/v1/health`

```sh
curl -sS "$BASE_URL/api/v1/health"
```

預期會看到：

```json
{
  "status": "ok",
  "version": "0.1.1",
  "storage_ready": true
}
```

重點：

- `status: ok`：API 正常回應。
- `storage_ready: true`：本機資料目錄可用。

### 步驟 2：準備一個 WAV 檔

支援格式為未壓縮 16-bit PCM WAV、單聲道或雙聲道、8–48 kHz。預設上限為 8 MiB、30 秒。

你可以使用 WebUI 錄音並下載自己的檔案，或在接有麥克風的主機錄製 3 秒：

```sh
arecord -D plughw:2,0 -d 3 -f S16_LE -r 16000 -c 1 sample.wav
```

若只想測試 API，不需要真人說話，可用 Python 產生 0.5 秒測試音：

```sh
python3 - <<'PY'
import math
import struct
import wave

rate = 16_000
with wave.open("sample.wav", "wb") as wav:
    wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
    frames = (
        struct.pack("<h", int(0.28 * 32767 * math.sin(2 * math.pi * 330 * i / rate)))
        for i in range(rate // 2)
    )
    wav.writeframes(b"".join(frames))
print("已建立 sample.wav")
PY
```

### 步驟 3：建立對話工作階段

Swagger 操作：`POST /api/v1/sessions`

```sh
curl -sS -X POST "$BASE_URL/api/v1/sessions"
```

回傳範例：

```json
{
  "id": "7f0e1a2b3c4d",
  "state": "ready",
  "created_at": "2026-01-01T00:00:00Z",
  "events": []
}
```

把 `id` 保存成環境變數。這個指令不需要安裝 `jq`：

```sh
SESSION_ID=$(curl -sS -X POST "$BASE_URL/api/v1/sessions" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "$SESSION_ID"
```

### 步驟 4：送出完整語音回合

Swagger 操作：`POST /api/v1/sessions/{session_id}/turns`

```sh
curl -sS -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @sample.wav \
  "$BASE_URL/api/v1/sessions/$SESSION_ID/turns" \
  | python3 -m json.tool
```

成功時會一次完成：

```text
WAV → VAD → ASR → 文字校正 → 語句結束判斷 → Agent → TTS
```

回傳的主要欄位：

- `transcript`：ASR 原始辨識文字。
- `corrected_text`：校正後文字。
- `end_detected`：系統是否判定語句已結束。
- `endpoint_reason`：結束判斷原因。
- `response`：Agent 的文字回覆。
- `audio_url`：TTS 產生的 WAV 相對網址。
- `latencies_ms`：各階段耗時，單位為毫秒。

目前預設 ASR、文字校正、Agent 與 TTS 是可重複測試的開發版 provider，不代表正式模型辨識效果。用 `/api/v1/capabilities` 可查看實際啟用的 provider 與限制。

### 步驟 5：下載 TTS 回覆

先從完整回合的結果取出 `audio_url`：

```sh
TURN_JSON=$(curl -sS -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @sample.wav \
  "$BASE_URL/api/v1/sessions/$SESSION_ID/turns")

AUDIO_URL=$(printf '%s' "$TURN_JSON" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["audio_url"])')

curl -sS "$BASE_URL$AUDIO_URL" -o response.wav
file response.wav
```

`response.wav` 是可播放的 16-bit PCM WAV。此裝置目前沒有喇叭時，可以下載到手機或其他電腦播放。

## 4. 常用操作速查

### 查看目前啟用的模型與限制

Swagger 操作：`GET /api/v1/capabilities`

```sh
curl -sS "$BASE_URL/api/v1/capabilities" | python3 -m json.tool
```

優先確認每個 provider 的：

- `ready`：是否可呼叫。
- `development`：是否為開發版替代實作。
- `limitations`：已知限制。
- `device`：目前執行裝置。

### 只測 VAD 是否偵測到聲音

Swagger 操作：`POST /api/v1/audio/vad`

```sh
curl -sS -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @sample.wav \
  "$BASE_URL/api/v1/audio/vad" \
  | python3 -m json.tool
```

回傳欄位：

- `voiced`：是否超過目前 VAD 門檻。
- `rms`：音訊能量。
- `duration_seconds`：音訊長度。

### 只測 ASR 語音轉文字

Swagger 操作：`POST /api/v1/audio/asr`

```sh
curl -sS -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @sample.wav \
  "$BASE_URL/api/v1/audio/asr" \
  | python3 -m json.tool
```

### 測試文字校正

Swagger 操作：`POST /api/v1/text/correct`

```sh
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"text":"  hello   agent "}' \
  "$BASE_URL/api/v1/text/correct" \
  | python3 -m json.tool
```

### 判斷一句話是否說完

Swagger 操作：`POST /api/v1/text/end-detect`

```sh
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"text":"你準備好了嗎？"}' \
  "$BASE_URL/api/v1/text/end-detect" \
  | python3 -m json.tool
```

`complete` 是提示資訊。完整語音回合目前仍會繼續執行 Agent 與 TTS，不會因 `complete: false` 自動累積下一段音訊。

### 只測 Agent 文字回覆

Swagger 操作：`POST /api/v1/agent/respond`

```sh
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"text":"請幫我整理今天的工作重點。"}' \
  "$BASE_URL/api/v1/agent/respond" \
  | python3 -m json.tool
```

這個端點最適合用來驗證新的 Agent adapter，不需要準備音訊。

### 只測 TTS 文字轉語音

Swagger 操作：`POST /api/v1/tts/synthesize`

```sh
TTS_JSON=$(curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，我是 Agent Speak。"}' \
  "$BASE_URL/api/v1/tts/synthesize")

printf '%s' "$TTS_JSON" | python3 -m json.tool
AUDIO_URL=$(printf '%s' "$TTS_JSON" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["audio_url"])')
curl -sS "$BASE_URL$AUDIO_URL" -o tts-response.wav
```

## 5. 說話者資料快速流程

說話者比對只供便利識別，不是生物辨識身分驗證，也不能用來做登入或存取控制。

### 建立說話者資料

Swagger 操作：`POST /api/v1/speakers`

```sh
SPEAKER_ID=$(curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"Allen","notes":"手機測試"}' \
  "$BASE_URL/api/v1/speakers" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["speaker"]["id"])')
echo "$SPEAKER_ID"
```

### 登錄聲音樣本

Swagger 操作：`POST /api/v1/speakers/{speaker_id}/samples`

```sh
curl -sS -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @sample.wav \
  "$BASE_URL/api/v1/speakers/$SPEAKER_ID/samples" \
  | python3 -m json.tool
```

### 比對聲音

Swagger 操作：`POST /api/v1/speakers/match`

```sh
curl -sS -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @sample.wav \
  "$BASE_URL/api/v1/speakers/match" \
  | python3 -m json.tool
```

結果中的：

- `match`：達到門檻的最接近資料；沒有結果時為 `null`。
- `score`：相似分數。
- `threshold`：本次比對門檻。

### 列出與刪除測試資料

```sh
curl -sS "$BASE_URL/api/v1/speakers" | python3 -m json.tool
curl -i -X DELETE "$BASE_URL/api/v1/speakers/$SPEAKER_ID"
```

刪除成功會回傳 HTTP `204 No Content`，並刪除該資料的本機樣本。

## 6. 查詢工作階段與即時事件

查詢目前工作階段狀態與保留的事件：

```sh
curl -sS "$BASE_URL/api/v1/sessions/$SESSION_ID" | python3 -m json.tool
```

即時事件使用 WebSocket：

```text
wss://ubuntu.tail9e662c.ts.net:8765/api/v1/sessions/{session_id}/events
```

連線後會先重播該工作階段目前保留的事件，再推送新事件。事件的 `sequence` 在同一個工作階段內遞增。若只想看處理結果，不需要自行連 WebSocket，直接使用完整回合 API 即可。

## 7. 錯誤怎麼看

所有 API 錯誤都使用相同格式：

```json
{
  "error": {
    "code": "unsupported_media_type",
    "message": "Content-Type must be audio/wav",
    "stage": "vad",
    "retryable": false,
    "details": {}
  }
}
```

先看：

1. HTTP 狀態碼。
2. `error.code`：程式可穩定判斷的代碼。
3. `error.message`：給人看的訊息。
4. `error.stage`：失敗階段。
5. `error.retryable`：相同輸入是否值得稍後重試。

常見狀況：

| HTTP | `error.code` | 原因與處理方式 |
|---|---|---|
| 400 | `invalid_wav` | 內容不是有效 WAV。重新匯出為未壓縮 16-bit PCM WAV。 |
| 404 | `session_not_found` | `session_id` 不存在或已被清理。重新建立工作階段。 |
| 409 | `turn_in_progress` | 同一工作階段已有回合執行中。等待完成，或建立另一個工作階段。 |
| 413 | `audio_too_large` / `audio_too_long` | 檔案超過大小或時間限制。縮短或重新取樣。 |
| 415 | `unsupported_media_type` / `unsupported_wav` | 缺少 `Content-Type: audio/wav`，或 WAV 格式不支援。 |
| 422 | `validation_error` | JSON 欄位缺失、為空、過長，或包含未允許欄位。 |
| 500 | `stage_failed` | provider 執行失敗。查看 `stage`，修正該階段 adapter 或稍後重試。 |

快速確認 Content-Type 錯誤：

```sh
curl -sS -X POST \
  -H "Content-Type: application/octet-stream" \
  --data-binary @sample.wav \
  "$BASE_URL/api/v1/audio/vad" \
  | python3 -m json.tool
```

## 8. 新手最常踩到的問題

### Swagger 的 Execute 按下去但回 415

上傳 WAV 的操作必須以 `audio/wav` 傳送。Swagger UI 選擇檔案後會自動設定；`curl` 必須加：

```sh
-H "Content-Type: audio/wav"
```

### 手機無法開啟網址

確認手機已開啟 Tailscale、登入同一個 Tailnet，並使用 HTTPS 網址。不要改成區網 IP，否則手機瀏覽器可能不允許麥克風 API。

### 上傳 MP3、M4A 或瀏覽器錄音失敗

API 不直接接受壓縮音訊。請先轉成 WAV，例如：

```sh
ffmpeg -i input.m4a -ac 1 -ar 16000 -sample_fmt s16 output.wav
```

### 有回傳文字，但內容不像真實辨識

先查 `/api/v1/capabilities`。若 ASR 的 `development` 是 `true`，目前使用的是開發版 provider，目的是驗證 API 串接與響應流程，不是評估正式模型準確率。

### 想直接看所有欄位與限制

- 人類操作：開啟 `/docs`。
- 程式產生 SDK 或型別：讀取 `/openapi.json`。
- 專案設計契約：閱讀 [`../spec/API.md`](../spec/API.md)。

## 9. 建議的測試順序

接新 ASR、Agent 或 TTS provider 時，依序測試：

1. `GET /api/v1/health`
2. `GET /api/v1/capabilities`
3. 對應的單階段 API
4. `POST /api/v1/sessions`
5. `POST /api/v1/sessions/{session_id}/turns`
6. 下載並驗證 `audio_url`
7. 視需要監聽 WebSocket 事件
8. 執行專案 smoke：

```sh
./scripts/health_smoke.sh
./scripts/smoke_api.sh
```

成功訊號分別為 `HEALTH_SMOKE_OK` 與 `API_SMOKE_OK`。
