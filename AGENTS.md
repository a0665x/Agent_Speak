# Agent onboarding

Agent Speak 是通用本機語音閘道，不綁定單一 LLM 或 Agent。

開始任何修改或操作前：

1. 先讀 [spec/PROJECT_MAP.md](spec/PROJECT_MAP.md) 與 [spec/project_herness.md](spec/project_herness.md)。
2. 要讓 Agent 使用麥克風、ASR、TTS 或喇叭時，讀 [skills/agent-speak/SKILL.md](skills/agent-speak/SKILL.md) 與 [spec/SKILL_AND_MCP.md](spec/SKILL_AND_MCP.md)。
3. 先執行 `./scripts/status.sh`；修改行為前執行 `./scripts/test.sh`。
4. 保留 `/api/v1` 契約與 provider 邊界，新增行為先寫失敗測試。
5. 未經使用者明確同意不得啟動麥克風或喇叭。
6. 不得提交 `.env`、credentials、錄音、聲紋/特徵、資料庫、runtime、模型權重、logs 或 Agent 私有狀態。

外部 Agent 的正確互動是：`listen_once → 由外部 Agent 自己推理/使用工具 → speak`。Gateway 目前的內建 Agent provider 是 development echo，不可宣稱為真正 LLM。
