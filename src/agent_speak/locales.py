"""Human-facing locale metadata for WebUI and OpenAPI documentation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SUPPORTED_LOCALES = ("en", "zh-TW", "ja", "ko")
DEFAULT_LOCALE = "en"


def normalize_locale(value: str | None) -> str:
    return value if value in SUPPORTED_LOCALES else DEFAULT_LOCALE


def _text(en: str, zh_tw: str, ja: str, ko: str) -> dict[str, str]:
    return {"en": en, "zh-TW": zh_tw, "ja": ja, "ko": ko}


API_INFO = {
    "description": _text(
        "Agent Speak is a local speech processing API. Beginners can create a session and upload PCM WAV audio to the full-turn endpoint, or call each processing stage separately. Every error uses one stable error envelope.",
        "Agent Speak 是本機語音處理 API。新手可先建立工作階段，再把 PCM WAV 上傳至完整對話端點；也可依序呼叫各階段端點。所有錯誤都使用一致的 error envelope。",
        "Agent Speak はローカル音声処理 API です。初めての場合はセッションを作成し、PCM WAV を完全ターン endpoint に送信できます。各処理段階を個別に呼び出すこともでき、すべてのエラーは共通の error envelope を使用します。",
        "Agent Speak는 로컬 음성 처리 API입니다. 먼저 세션을 만들고 PCM WAV를 전체 턴 endpoint에 업로드하거나 각 처리 단계를 개별 호출할 수 있습니다. 모든 오류는 동일한 error envelope 형식을 사용합니다.",
    )
}


DOCS_UI_TEXT = {
    "en": {"title": "Agent Speak API Explorer", "language": "API language", "home": "Project Home"},
    "zh-TW": {"title": "Agent Speak API Explorer", "language": "API 語言", "home": "專案首頁"},
    "ja": {"title": "Agent Speak API Explorer", "language": "API の言語", "home": "プロジェクトホーム"},
    "ko": {"title": "Agent Speak API Explorer", "language": "API 언어", "home": "프로젝트 홈"},
}


TAG_KEYS = ("system", "conversation", "audio", "text", "speakers", "artifacts", "tts_clone")
TAG_TEXT = {
    "system": {
        "name": _text("System", "系統", "システム", "시스템"),
        "description": _text(
            "Check service health and the processing capabilities currently enabled.",
            "確認服務健康狀態與目前實際啟用的處理能力。",
            "サービスの稼働状態と現在有効な処理能力を確認します。",
            "서비스 상태와 현재 활성화된 처리 기능을 확인합니다.",
        ),
    },
    "conversation": {
        "name": _text("Conversation Flow", "對話流程", "会話フロー", "대화 흐름"),
        "description": _text(
            "Create sessions and run a complete spoken conversation turn.",
            "建立工作階段並一次執行完整語音對話流程。",
            "セッションを作成し、音声会話の完全な 1 ターンを実行します。",
            "세션을 만들고 전체 음성 대화 턴을 실행합니다.",
        ),
    },
    "audio": {
        "name": _text("Audio Stages", "語音階段", "音声処理", "오디오 단계"),
        "description": _text(
            "Test the VAD and ASR audio stages independently.",
            "單獨測試 VAD 與 ASR 語音處理階段。",
            "VAD と ASR の音声処理段階を個別にテストします。",
            "VAD 및 ASR 오디오 처리 단계를 개별 테스트합니다.",
        ),
    },
    "text": {
        "name": _text("Text Stages", "文字階段", "テキスト処理", "텍스트 단계"),
        "description": _text(
            "Test correction, endpoint detection, Agent response, and TTS independently.",
            "單獨測試文字校正、結束判斷、Agent 與 TTS。",
            "テキスト補正、終端判定、Agent 応答、TTS を個別にテストします。",
            "텍스트 교정, 종점 감지, Agent 응답 및 TTS를 개별 테스트합니다.",
        ),
    },
    "speakers": {
        "name": _text("Speakers", "說話者", "話者", "화자"),
        "description": _text(
            "Manage local convenience-identification records; this is not biometric authentication.",
            "管理本機便利識別資料；不是生物辨識身分驗證。",
            "ローカルの簡易識別データを管理します。生体認証ではありません。",
            "로컬 편의 식별 데이터를 관리합니다. 생체 인증이 아닙니다.",
        ),
    },
    "artifacts": {
        "name": _text("Audio Artifacts", "音訊成品", "音声成果物", "오디오 결과물"),
        "description": _text(
            "Read locally generated TTS WAV audio.",
            "讀取 TTS 產生的本機 WAV 音訊。",
            "TTS が生成したローカル WAV 音声を取得します。",
            "TTS가 생성한 로컬 WAV 오디오를 가져옵니다.",
        ),
    },
    "tts_clone": {
        "name": _text("TTS Clone", "TTS 克隆", "TTS クローン", "TTS 클론"),
        "description": _text(
            "Check VoxCPM2 readiness, validate a transient voice reference, and generate non-persistent WAV audio.",
            "檢查 VoxCPM2 就緒狀態、驗證暫時參考錄音並產生不落地保存的 WAV。",
            "VoxCPM2 の準備状態を確認し、一時的な音声参照を検証して、保存しない WAV 音声を生成します。",
            "VoxCPM2 준비 상태를 확인하고 임시 음성 참조를 검증하며 저장하지 않는 WAV 오디오를 생성합니다.",
        ),
    },
}


OPERATION_TAGS = {
    "GET /api/v1/health": "system",
    "GET /api/v1/capabilities": "system",
    "GET /api/v1/models": "system",
    "PUT /api/v1/models/active": "system",
    "POST /api/v1/sessions": "conversation",
    "GET /api/v1/sessions/{session_id}": "conversation",
    "POST /api/v1/sessions/{session_id}/turns": "conversation",
    "POST /api/v1/audio/vad": "audio",
    "POST /api/v1/audio/asr": "audio",
    "POST /api/v1/text/correct": "text",
    "POST /api/v1/text/end-detect": "text",
    "POST /api/v1/agent/respond": "text",
    "POST /api/v1/tts/synthesize": "text",
    "GET /api/v1/artifacts/{name}": "artifacts",
    "GET /api/v1/tts-clone/status": "tts_clone",
    "POST /api/v1/tts-clone/reference/validate": "tts_clone",
    "POST /api/v1/tts-clone/synthesize": "tts_clone",
    "POST /api/v1/speakers": "speakers",
    "GET /api/v1/speakers": "speakers",
    "GET /api/v1/speakers/{speaker_id}": "speakers",
    "PATCH /api/v1/speakers/{speaker_id}": "speakers",
    "DELETE /api/v1/speakers/{speaker_id}": "speakers",
    "POST /api/v1/speakers/{speaker_id}/samples": "speakers",
    "POST /api/v1/speakers/match": "speakers",
}


OPERATION_TEXT = {
    "GET /api/v1/health": _text(
        "Check service health|Input: optional verbose query parameter. Output: version, status, and local storage readiness.",
        "檢查服務健康狀態|輸入：可選 verbose 查詢參數。輸出：版本、狀態與本機儲存是否就緒。",
        "サービスの稼働状態を確認|入力：任意の verbose query parameter。出力：バージョン、状態、ローカルストレージの準備状況。",
        "서비스 상태 확인|입력: 선택적 verbose query parameter. 출력: 버전, 상태 및 로컬 저장소 준비 여부.",
    ),
    "GET /api/v1/capabilities": _text(
        "View processing capabilities|Input: none. Output: active providers, versions, devices, and limits for all six processing stages.",
        "查看目前處理能力|輸入：無。輸出：六個處理階段實際啟用的提供者、版本、裝置與限制。",
        "処理能力を表示|入力：なし。出力：6 つの処理段階で有効な provider、バージョン、device、制限。",
        "처리 기능 보기|입력: 없음. 출력: 6개 처리 단계의 활성 provider, 버전, device 및 제한 사항.",
    ),
    "GET /api/v1/models": _text(
        "View available inference models|Input: none. Output: selectable ASR and correction models plus the current load, device, and lease state.",
        "查看可用推論模型|輸入：無。輸出：可選的 ASR 與校正模型，以及目前載入、裝置與租用狀態。",
        "利用可能な推論モデルを表示|入力：なし。出力：選択可能な ASR・補正モデルと、現在の読み込み、device、lease 状態。",
        "사용 가능한 추론 모델 보기|입력: 없음. 출력: 선택 가능한 ASR·교정 모델과 현재 로드, device, lease 상태.",
    ),
    "PUT /api/v1/models/active": _text(
        "Switch active inference models|Input: ASR model and correction policy. Output: the complete switched or loading model state. No separate submit step is required by clients.",
        "切換啟用中的推論模型|輸入：ASR 模型與校正策略。輸出：切換後或載入中的完整模型狀態；client 不需額外 submit。",
        "有効な推論モデルを切り替え|入力：ASR model と補正 policy。出力：切り替え後または読み込み中の完全な model state。client 側の追加 submit は不要です。",
        "활성 추론 모델 전환|입력: ASR model과 교정 policy. 출력: 전환 후 또는 로드 중인 전체 model state. client의 별도 submit은 필요 없습니다.",
    ),
    "POST /api/v1/sessions": _text(
        "Create a conversation session|Input: optional speech language, ASR model, and correction policy. Output: a new session identifier, state, frozen inference choices, and event list. Every selected value is frozen for the session and cannot change while realtime listening is active.",
        "建立對話工作階段|輸入：選填語音語言、ASR 模型與校正策略。輸出：新的工作階段識別碼、狀態、固定推論選項與事件清單。所有選定值都會在工作階段固定，即時聆聽期間不可變更。",
        "会話セッションを作成|入力：任意の音声言語、ASR model、補正 policy。出力：新しい session ID、状態、固定された推論設定、event 一覧。選択値は session に固定され、realtime listening 中は変更できません。",
        "대화 세션 만들기|입력: 선택적 음성 언어, ASR model 및 교정 policy. 출력: 새 session ID, 상태, 고정된 추론 설정 및 event 목록. 선택값은 session에 고정되며 realtime listening 중에는 변경할 수 없습니다.",
    ),
    "GET /api/v1/sessions/{session_id}": _text(
        "Get a conversation session|Input: session identifier. Output: current state and retained pipeline events.",
        "取得對話工作階段|輸入：工作階段識別碼。輸出：目前狀態與已保留的流程事件。",
        "会話セッションを取得|入力：session ID。出力：現在の状態と保持されている pipeline event。",
        "대화 세션 가져오기|입력: session ID. 출력: 현재 상태와 보관된 pipeline event.",
    ),
    "POST /api/v1/sessions/{session_id}/turns": _text(
        "Run a complete speech turn|Input: PCM WAV and session identifier. Output: transcript, correction, Agent response, WAV URL, and stage latencies.",
        "執行完整語音回合|輸入：PCM WAV 與工作階段識別碼。輸出：辨識、校正、Agent 回覆、WAV 網址與各階段耗時。",
        "完全な音声ターンを実行|入力：PCM WAV と session ID。出力：文字起こし、補正、Agent 応答、WAV URL、各段階の latency。",
        "전체 음성 턴 실행|입력: PCM WAV 및 session ID. 출력: 전사, 교정, Agent 응답, WAV URL 및 단계별 latency.",
    ),
    "POST /api/v1/audio/vad": _text(
        "Detect voice in audio|Input: PCM WAV audio. Output: voice detection, RMS energy, and audio duration.",
        "偵測音訊中的人聲|輸入：PCM WAV 音訊。輸出：是否有人聲、RMS 能量與音訊秒數。",
        "音声内の発話を検出|入力：PCM WAV 音声。出力：発話の有無、RMS energy、音声時間。",
        "오디오에서 음성 감지|입력: PCM WAV 오디오. 출력: 음성 감지 여부, RMS energy 및 오디오 길이.",
    ),
    "POST /api/v1/audio/asr": _text(
        "Transcribe speech to text|Input: PCM WAV audio. Output: ASR transcript. This standalone endpoint uses the configured server default and does not inherit the Web UI language.",
        "將語音辨識為文字|輸入：PCM WAV 音訊。輸出：ASR 辨識文字。此獨立端點使用伺服器設定的預設語言，不會繼承 Web UI 語言。",
        "音声をテキスト化|入力：PCM WAV 音声。出力：ASR 文字起こし。この単独 endpoint は server 設定の既定言語を使用し、Web UI の言語を継承しません。",
        "음성을 텍스트로 전사|입력: PCM WAV 오디오. 출력: ASR 전사문. 이 독립 endpoint는 server 설정 기본 언어를 사용하며 Web UI 언어를 상속하지 않습니다.",
    ),
    "POST /api/v1/text/correct": _text(
        "Correct recognized text|Input: recognized text to clean up. Output: corrected, more readable text.",
        "校正辨識文字|輸入：要清理的辨識文字。輸出：校正後、較易閱讀的文字。",
        "認識テキストを補正|入力：整形する認識テキスト。出力：補正され読みやすくなったテキスト。",
        "인식 텍스트 교정|입력: 정리할 인식 텍스트. 출력: 교정되어 읽기 쉬운 텍스트.",
    ),
    "POST /api/v1/text/end-detect": _text(
        "Detect utterance completion|Input: corrected text. Output: completion decision and reason.",
        "判斷語句是否結束|輸入：校正後文字。輸出：是否已完成語句及判定原因。",
        "発話の完了を判定|入力：補正済みテキスト。出力：完了判定とその理由。",
        "발화 완료 감지|입력: 교정된 텍스트. 출력: 완료 여부와 판단 이유.",
    ),
    "POST /api/v1/agent/respond": _text(
        "Generate an Agent response|Input: user text. Output: text produced by the active Agent provider.",
        "產生 Agent 回覆|輸入：使用者文字。輸出：目前 Agent 提供者產生的文字回覆。",
        "Agent 応答を生成|入力：ユーザーテキスト。出力：現在の Agent provider が生成したテキスト応答。",
        "Agent 응답 생성|입력: 사용자 텍스트. 출력: 현재 Agent provider가 생성한 텍스트 응답.",
    ),
    "POST /api/v1/tts/synthesize": _text(
        "Synthesize text to speech|Input: text to speak. Output: local URL for downloading or playing the generated WAV.",
        "將文字合成語音|輸入：要朗讀的文字。輸出：可下載或播放的 WAV 站內網址。",
        "テキストを音声合成|入力：読み上げるテキスト。出力：生成 WAV を取得または再生するローカル URL。",
        "텍스트를 음성으로 합성|입력: 읽을 텍스트. 출력: 생성된 WAV를 내려받거나 재생할 로컬 URL.",
    ),
    "GET /api/v1/tts-clone/status": _text(
        "Check TTS clone readiness|Input: none. Output: GPU mode, accelerator, worker, and VoxCPM2 readiness.",
        "檢查 TTS 克隆就緒狀態|輸入：無。輸出：GPU 模式、加速器、worker 與 VoxCPM2 就緒狀態。",
        "TTS クローンの準備状態を確認|入力：なし。出力：GPU mode、accelerator、worker、VoxCPM2 の準備状態。",
        "TTS 클론 준비 상태 확인|입력: 없음. 출력: GPU mode, accelerator, worker 및 VoxCPM2 준비 상태.",
    ),
    "POST /api/v1/tts-clone/reference/validate": _text(
        "Validate a clone reference|Input: transient PCM WAV. Output: duration, level, voiced ratio, and bounded quality result; audio is not stored.",
        "驗證克隆參考錄音|輸入：暫時性的 PCM WAV。輸出：長度、音量、人聲比例與有限集合的品質結果；音訊不會保存。",
        "クローン参照音声を検証|入力：一時的な PCM WAV。出力：長さ、音量、発話比率、定義済みの品質結果。音声は保存されません。",
        "클론 참조 음성 검증|입력: 임시 PCM WAV. 출력: 길이, 음량, 음성 비율 및 제한된 품질 결과. 오디오는 저장되지 않습니다.",
    ),
    "POST /api/v1/tts-clone/synthesize": _text(
        "Generate cloned or default TTS|Input: text, style cues, clone toggle, and optional reference. Output: a non-persistent 48 kHz WAV.",
        "產生克隆或預設 TTS|輸入：文字、語氣提示、克隆開關與選填參考錄音。輸出：不落地保存的 48 kHz WAV。",
        "クローンまたは既定音声の TTS を生成|入力：テキスト、style cue、clone 切替、任意の参照音声。出力：保存しない 48 kHz WAV。",
        "클론 또는 기본 TTS 생성|입력: 텍스트, style cue, 클론 전환 및 선택적 참조 음성. 출력: 저장하지 않는 48 kHz WAV.",
    ),
    "GET /api/v1/artifacts/{name}": _text(
        "Get generated WAV audio|Input: WAV filename returned by TTS. Output: binary audio/wav content.",
        "取得合成 WAV 音訊|輸入：TTS 回傳的 WAV 檔名。輸出：audio/wav 二進位音訊。",
        "生成 WAV 音声を取得|入力：TTS が返した WAV filename。出力：audio/wav binary。",
        "생성된 WAV 오디오 가져오기|입력: TTS가 반환한 WAV filename. 출력: audio/wav binary.",
    ),
    "POST /api/v1/speakers": _text(
        "Create a speaker record|Input: name and optional notes. Output: new local speaker record; this is not authentication.",
        "建立說話者資料|輸入：名稱與選填備註。輸出：新建的本機說話者資料；此功能不是身分驗證。",
        "話者データを作成|入力：名前と任意のメモ。出力：新しいローカル話者データ。認証用途ではありません。",
        "화자 데이터 만들기|입력: 이름과 선택적 메모. 출력: 새 로컬 화자 데이터이며 인증 기능이 아닙니다.",
    ),
    "GET /api/v1/speakers": _text(
        "List speaker records|Input: none. Output: all local speaker records and a safety notice.",
        "列出說話者資料|輸入：無。輸出：所有本機說話者資料與安全提醒。",
        "話者データを一覧表示|入力：なし。出力：すべてのローカル話者データと安全上の注意。",
        "화자 데이터 목록|입력: 없음. 출력: 모든 로컬 화자 데이터와 안전 안내.",
    ),
    "GET /api/v1/speakers/{speaker_id}": _text(
        "Get a speaker record|Input: speaker identifier. Output: selected local record and sample count.",
        "取得說話者資料|輸入：說話者識別碼。輸出：指定的本機資料與樣本數。",
        "話者データを取得|入力：speaker ID。出力：指定したローカルデータと sample count。",
        "화자 데이터 가져오기|입력: speaker ID. 출력: 선택한 로컬 데이터와 sample count.",
    ),
    "PATCH /api/v1/speakers/{speaker_id}": _text(
        "Update a speaker record|Input: speaker identifier, complete name, and notes. Output: updated record.",
        "更新說話者資料|輸入：說話者識別碼、完整名稱與備註。輸出：更新後的資料。",
        "話者データを更新|入力：speaker ID、完全な名前、メモ。出力：更新済みデータ。",
        "화자 데이터 업데이트|입력: speaker ID, 전체 이름 및 메모. 출력: 업데이트된 데이터.",
    ),
    "DELETE /api/v1/speakers/{speaker_id}": _text(
        "Delete a speaker record|Input: speaker identifier. Output: 204 on success; local samples are also deleted.",
        "刪除說話者資料|輸入：說話者識別碼。輸出：成功時為 204，並刪除其本機樣本。",
        "話者データを削除|入力：speaker ID。出力：成功時は 204。ローカル sample も削除されます。",
        "화자 데이터 삭제|입력: speaker ID. 출력: 성공 시 204이며 로컬 sample도 삭제됩니다.",
    ),
    "POST /api/v1/speakers/{speaker_id}/samples": _text(
        "Enroll a speaker voice sample|Input: speaker identifier and PCM WAV. Output: record with updated sample count; convenience identification only.",
        "登錄說話者語音樣本|輸入：說話者識別碼與 PCM WAV。輸出：樣本數已更新的資料；只供便利識別。",
        "話者の音声 sample を登録|入力：speaker ID と PCM WAV。出力：sample count が更新されたデータ。簡易識別専用です。",
        "화자 음성 sample 등록|입력: speaker ID 및 PCM WAV. 출력: sample count가 업데이트된 데이터이며 편의 식별 전용입니다.",
    ),
    "POST /api/v1/speakers/match": _text(
        "Match a speaker voice|Input: PCM WAV. Output: nearest record above the threshold, score, and threshold; not authentication.",
        "比對說話者語音|輸入：PCM WAV。輸出：最接近且達門檻的本機資料、分數與門檻；不是身分驗證。",
        "話者音声を照合|入力：PCM WAV。出力：threshold 以上で最も近いローカルデータ、score、threshold。認証ではありません。",
        "화자 음성 일치 확인|입력: PCM WAV. 출력: threshold 이상인 가장 가까운 로컬 데이터, score 및 threshold이며 인증이 아닙니다.",
    ),
}


FIELD_TEXT = {
    "HTTPValidationError.detail": _text("Request validation errors.", "請求驗證錯誤清單。", "request validation error の一覧。", "요청 validation 오류 목록."),
    "ValidationError.loc": _text("Location of the invalid value in the request.", "請求中無效值的位置。", "request 内の無効な値の位置。", "요청에서 잘못된 값의 위치."),
    "ValidationError.msg": _text("Human-readable validation error message.", "便於閱讀的驗證錯誤訊息。", "読みやすい validation error message。", "사람이 읽을 수 있는 validation 오류 메시지."),
    "ValidationError.type": _text("Stable validation error type.", "穩定的驗證錯誤類型。", "安定した validation error type。", "안정적인 validation 오류 유형."),
    "ValidationError.input": _text("Invalid input value when it is safe to include.", "可安全顯示時提供的無效輸入值。", "安全に表示できる場合の無効な入力値。", "안전하게 표시할 수 있는 경우의 잘못된 입력값."),
    "ValidationError.ctx": _text("Additional validation context when available.", "可用時提供的額外驗證資訊。", "利用可能な追加 validation context。", "사용 가능한 추가 validation 정보."),
    "CapabilitiesResponse.providers": _text("Active providers for the six processing stages.", "六個處理階段的實際提供者。", "6 つの処理段階で有効な provider。", "6개 처리 단계의 활성 provider."),
    "CapabilitiesResponse.speaker_matching_notice": _text("Safety notice for speaker matching.", "說話者比對安全提醒。", "話者照合に関する安全上の注意。", "화자 일치 확인 안전 안내."),
    "EndDetectOutput.complete": _text("Whether the user is considered to have finished speaking.", "是否判定使用者已說完。", "ユーザーが話し終えたと判定されたか。", "사용자가 발화를 마쳤다고 판단했는지 여부."),
    "EndDetectOutput.reason": _text("Reason for the completion decision.", "語句結束判定原因。", "完了判定の理由。", "완료 판단 이유."),
    "HealthResponse.status": _text("Service health status.", "服務健康狀態。", "サービスの稼働状態。", "서비스 상태."),
    "HealthResponse.version": _text("Agent Speak version.", "Agent Speak 版本。", "Agent Speak のバージョン。", "Agent Speak 버전."),
    "HealthResponse.storage_ready": _text("Whether the local data directory is ready.", "本機資料目錄是否就緒。", "ローカルデータ directory が準備済みか。", "로컬 데이터 directory 준비 여부."),
    "PipelineEvent.sequence": _text("Increasing event sequence number within the session.", "工作階段內遞增的事件序號。", "session 内で増加する event sequence number。", "session 내에서 증가하는 event sequence number."),
    "PipelineEvent.type": _text("Pipeline event type.", "流程事件類型。", "pipeline event type。", "pipeline event type."),
    "PipelineEvent.stage": _text("Related processing stage, or null when not applicable.", "相關處理階段；不適用時為 null。", "関連する処理段階。該当しない場合は null。", "관련 처리 단계이며 해당하지 않으면 null."),
    "PipelineEvent.at": _text("UTC event timestamp.", "UTC 事件時間。", "UTC の event timestamp。", "UTC event timestamp."),
    "PipelineEvent.elapsed_ms": _text("Stage latency in milliseconds.", "階段耗時（毫秒）。", "処理段階の latency（milliseconds）。", "단계 latency(milliseconds)."),
    "PipelineEvent.data": _text("Additional structured event data.", "事件附加的結構化資料。", "追加の構造化 event data。", "추가 구조화 event data."),
    "ProviderCapability.stage": _text("Speech pipeline stage.", "語音流程階段。", "音声 pipeline の処理段階。", "음성 pipeline 단계."),
    "ProviderCapability.name": _text("Active provider name.", "目前使用的提供者名稱。", "現在使用中の provider 名。", "현재 사용 중인 provider 이름."),
    "ProviderCapability.ready": _text("Whether the provider can be called.", "提供者是否可呼叫。", "provider を呼び出せる状態か。", "provider 호출 가능 여부."),
    "ProviderCapability.development": _text("Whether this is a limited development provider.", "是否為功能受限的開發版提供者。", "機能制限のある development provider か。", "기능이 제한된 development provider 여부."),
    "ProviderCapability.limitations": _text("Known provider limitations.", "已知限制。", "既知の provider 制限。", "알려진 provider 제한 사항."),
    "ProviderCapability.version": _text("Provider version.", "提供者版本。", "provider のバージョン。", "provider 버전."),
    "ProviderCapability.device": _text("Inference device.", "推論執行裝置。", "推論 device。", "추론 device."),
    "SessionSummary.id": _text("Session identifier.", "工作階段識別碼。", "session ID。", "session ID."),
    "SessionSummary.state": _text("Current session state.", "工作階段目前狀態。", "現在の session state。", "현재 session state."),
    "SessionSummary.speech_language": _text(
        "Speech language frozen for the session at creation time.",
        "建立時為工作階段固定的語音語言。",
        "作成時に session に固定された音声言語。",
        "생성 시 session에 고정된 음성 언어.",
    ),
    "SessionSummary.asr_model": _text(
        "ASR model frozen for the session at creation time.",
        "建立時為工作階段固定的 ASR 模型。",
        "作成時に session に固定された ASR model。",
        "생성 시 session에 고정된 ASR model.",
    ),
    "SessionSummary.correction_model": _text(
        "Correction policy frozen for the session at creation time.",
        "建立時為工作階段固定的校正策略。",
        "作成時に session に固定された補正 policy。",
        "생성 시 session에 고정된 교정 policy.",
    ),
    "SessionSummary.created_at": _text("Session creation time in UTC.", "UTC 工作階段建立時間。", "UTC の session 作成時刻。", "UTC session 생성 시간."),
    "SessionSummary.events": _text("Pipeline events currently retained for the session.", "目前保留的流程事件。", "session に現在保持されている pipeline event。", "session에 현재 보관된 pipeline event."),
    "SpeakerCreate.name": _text("Speaker display name, 1 to 100 characters.", "說話者顯示名稱，1 至 100 字元。", "話者の表示名。1～100 文字。", "화자 표시 이름, 1~100자."),
    "SpeakerCreate.notes": _text("Optional notes, up to 500 characters.", "選填備註，最多 500 字元。", "任意のメモ。最大 500 文字。", "선택적 메모, 최대 500자."),
    "SpeakerUpdate.name": _text("Updated speaker display name.", "更新後的顯示名稱。", "更新後の話者表示名。", "업데이트된 화자 표시 이름."),
    "SpeakerUpdate.notes": _text("Updated optional notes.", "更新後的選填備註。", "更新後の任意メモ。", "업데이트된 선택적 메모."),
    "SpeakerProfile.id": _text("Speaker record identifier.", "說話者資料識別碼。", "話者データ ID。", "화자 데이터 ID."),
    "SpeakerProfile.name": _text("Speaker display name.", "說話者顯示名稱。", "話者の表示名。", "화자 표시 이름."),
    "SpeakerProfile.notes": _text("Speaker notes.", "說話者備註。", "話者のメモ。", "화자 메모."),
    "SpeakerProfile.created_at": _text("Record creation time in UTC.", "UTC 資料建立時間。", "UTC のデータ作成時刻。", "UTC 데이터 생성 시간."),
    "SpeakerProfile.sample_count": _text("Number of enrolled voice samples.", "已登錄語音樣本數。", "登録済み音声 sample の数。", "등록된 음성 sample 수."),
    "SpeakerEnvelope.speaker": _text("Speaker record.", "說話者資料。", "話者データ。", "화자 데이터."),
    "SpeakerEnvelope.notice": _text("Convenience-identification safety notice.", "便利識別而非身分驗證的提醒。", "簡易識別であり認証ではないことを示す注意。", "편의 식별이며 인증이 아니라는 안내."),
    "SpeakerList.speakers": _text("Local speaker records.", "本機說話者資料清單。", "ローカル話者データの一覧。", "로컬 화자 데이터 목록."),
    "SpeakerList.notice": _text("Convenience-identification safety notice.", "便利識別而非身分驗證的提醒。", "簡易識別であり認証ではないことを示す注意。", "편의 식별이며 인증이 아니라는 안내."),
    "SpeakerMatchEnvelope.match": _text("Closest record above the threshold, or null when there is no match.", "最接近且達門檻的資料；無結果時為 null。", "threshold 以上で最も近いデータ。該当なしの場合は null。", "threshold 이상인 가장 가까운 데이터이며 결과가 없으면 null."),
    "SpeakerMatchEnvelope.score": _text("Similarity score, or null when there is no match.", "相似分數；無結果時為 null。", "similarity score。該当なしの場合は null。", "similarity score이며 결과가 없으면 null."),
    "SpeakerMatchEnvelope.threshold": _text("Matching threshold used for this request.", "本次使用的比對門檻。", "この request で使用した matching threshold。", "이번 request에 사용한 matching threshold."),
    "SpeakerMatchEnvelope.notice": _text("Convenience-identification safety notice.", "便利識別而非身分驗證的提醒。", "簡易識別であり認証ではないことを示す注意。", "편의 식별이며 인증이 아니라는 안내."),
    "TextInput.text": _text("Non-empty UTF-8 text to process, up to 20,000 characters.", "要處理的 UTF-8 文字，不可為空，最多 20,000 個字元。", "処理する空でない UTF-8 テキスト。最大 20,000 文字。", "처리할 비어 있지 않은 UTF-8 텍스트, 최대 20,000자."),
    "TextOutput.text": _text("Processed text result.", "處理後的文字結果。", "処理後のテキスト結果。", "처리된 텍스트 결과."),
    "TtsOutput.audio_url": _text("Local URL for the synthesized WAV.", "可取得合成 WAV 的站內網址。", "合成 WAV を取得するローカル URL。", "합성 WAV를 가져올 로컬 URL."),
    "TtsOutput.content_type": _text("Audio MIME type.", "音訊 MIME 類型。", "音声 MIME type。", "오디오 MIME type."),
    "TurnResponse.transcript": _text("Raw ASR transcript.", "ASR 原始辨識文字。", "ASR の未補正文字起こし。", "ASR 원본 전사문."),
    "TurnResponse.corrected_text": _text("Corrected transcript.", "校正後文字。", "補正済み文字起こし。", "교정된 전사문."),
    "TurnResponse.end_detected": _text("Whether the utterance was considered complete.", "是否判定語句結束。", "発話が完了したと判定されたか。", "발화가 완료되었다고 판단했는지 여부."),
    "TurnResponse.endpoint_reason": _text("Reason for the endpoint decision.", "語句結束判定原因。", "endpoint 判定の理由。", "endpoint 판단 이유."),
    "TurnResponse.response": _text("Agent text response.", "Agent 文字回覆。", "Agent のテキスト応答。", "Agent 텍스트 응답."),
    "TurnResponse.audio_url": _text("Local URL for the Agent response WAV.", "Agent 回覆 WAV 的站內網址。", "Agent 応答 WAV のローカル URL。", "Agent 응답 WAV의 로컬 URL."),
    "TurnResponse.latencies_ms": _text("Latency for each processing stage in milliseconds.", "各處理階段耗時（毫秒）。", "各処理段階の latency（milliseconds）。", "각 처리 단계의 latency(milliseconds)."),
    "VadOutput.voiced": _text("Whether voice was detected in the audio.", "音訊中是否偵測到人聲。", "音声内で発話が検出されたか。", "오디오에서 음성이 감지되었는지 여부."),
    "VadOutput.rms": _text("Root mean square audio energy.", "音訊均方根能量。", "音声の RMS energy。", "오디오 RMS energy."),
    "VadOutput.duration_seconds": _text("Audio duration in seconds.", "音訊長度（秒）。", "音声時間（seconds）。", "오디오 길이(seconds)."),
    "ASRModelOption.id": _text("Stable ASR model identifier.", "穩定的 ASR 模型識別碼。", "安定した ASR モデル ID。", "안정적인 ASR 모델 ID."),
    "ASRModelOption.label": _text("Human-readable ASR model name.", "方便閱讀的 ASR 模型名稱。", "表示用の ASR モデル名。", "사용자용 ASR 모델 이름."),
    "ASRModelOption.description": _text("ASR model purpose and strengths.", "ASR 模型用途與優勢。", "ASR モデルの用途と強み。", "ASR 모델의 용도와 강점."),
    "ASRModelOption.ready": _text("Whether this ASR model can currently be selected.", "此 ASR 模型目前是否可選。", "この ASR モデルを現在選択できるか。", "현재 이 ASR 모델을 선택할 수 있는지 여부."),
    "CorrectionModelOption.id": _text("Stable correction policy identifier.", "穩定的校正策略識別碼。", "安定した補正 policy ID。", "안정적인 교정 policy ID."),
    "CorrectionModelOption.label": _text("Human-readable correction policy name.", "方便閱讀的校正策略名稱。", "表示用の補正 policy 名。", "사용자용 교정 policy 이름."),
    "CorrectionModelOption.description": _text("Correction policy behavior.", "校正策略行為說明。", "補正 policy の動作。", "교정 policy 동작."),
    "CorrectionModelOption.ready": _text("Whether this correction policy can currently be selected.", "此校正策略目前是否可選。", "この補正 policy を現在選択できるか。", "현재 이 교정 policy를 선택할 수 있는지 여부."),
    "ActiveModelSelection.asr_model": _text("Currently active ASR model, or null when unavailable.", "目前啟用的 ASR 模型；無法使用時為 null。", "現在有効な ASR モデル。利用不可の場合は null。", "현재 활성 ASR 모델이며 사용할 수 없으면 null."),
    "ActiveModelSelection.correction_model": _text("Currently selected correction policy.", "目前選用的校正策略。", "現在選択中の補正 policy。", "현재 선택된 교정 policy."),
    "ActiveModelSelection.requested_asr_model": _text("ASR model currently being loaded, if any.", "目前正在載入的 ASR 模型；沒有時為 null。", "読み込み中の ASR モデル。ない場合は null。", "현재 로드 중인 ASR 모델이며 없으면 null."),
    "ActiveModelSelection.state": _text("Current ASR model lifecycle stage.", "目前 ASR 模型生命週期階段。", "現在の ASR モデル lifecycle stage。", "현재 ASR 모델 lifecycle 단계."),
    "ActiveModelSelection.leased_by": _text("Realtime session holding the ASR model lease, if any.", "持有 ASR 模型租用權的 realtime 工作階段；沒有時為 null。", "ASR モデル lease を保持する realtime session。ない場合は null。", "ASR 모델 lease를 보유한 realtime session이며 없으면 null."),
    "ActiveModelSelection.device": _text("Inference device reported by the ASR worker.", "ASR worker 回報的推論裝置。", "ASR worker が報告した推論 device。", "ASR worker가 보고한 추론 device."),
    "ActiveModelSelection.error_code": _text("Bounded activation error code, if any.", "有限集合的啟用錯誤代碼；沒有時為 null。", "定義済みの activation error code。ない場合は null。", "정의된 activation error code이며 없으면 null."),
    "ModelCatalog.asr": _text("Selectable ASR models.", "可選的 ASR 模型。", "選択可能な ASR モデル。", "선택 가능한 ASR 모델."),
    "ModelCatalog.correction": _text("Selectable correction policies.", "可選的校正策略。", "選択可能な補正 policy。", "선택 가능한 교정 policy."),
    "ModelCatalog.active": _text("Active selections and model lifecycle state.", "啟用中的選項與模型生命週期狀態。", "有効な選択と model lifecycle state。", "활성 선택과 model lifecycle 상태."),
    "ModelActivationInput.asr_model": _text("ASR model to activate.", "要啟用的 ASR 模型。", "有効にする ASR モデル。", "활성화할 ASR 모델."),
    "ModelActivationInput.correction_model": _text("Correction policy to select.", "要選用的校正策略。", "選択する補正 policy。", "선택할 교정 policy."),
    "TTSCloneStatus.gpu_mode": _text("Exclusive GPU workload mode.", "目前互斥的 GPU 工作模式。", "排他的な GPU workload mode。", "배타적 GPU workload mode."),
    "TTSCloneStatus.accelerator": _text("Effective inference accelerator.", "目前有效的推論加速器。", "有効な推論 accelerator。", "현재 유효한 추론 accelerator."),
    "TTSCloneStatus.state": _text("VoxCPM2 worker and model lifecycle state.", "VoxCPM2 worker 與模型生命週期狀態。", "VoxCPM2 worker と model lifecycle state。", "VoxCPM2 worker 및 model lifecycle 상태."),
    "TTSCloneStatus.model": _text("TTS clone model identifier.", "TTS 克隆模型識別碼。", "TTS clone model ID。", "TTS 클론 model ID."),
    "TTSCloneStatus.device": _text("Model inference device.", "模型推論裝置。", "モデル推論 device。", "모델 추론 device."),
    "TTSCloneStatus.ready": _text("Whether speech can be generated now.", "目前是否可產生語音。", "現在音声を生成できるか。", "현재 음성 생성 가능 여부."),
    "TTSCloneStatus.error_code": _text("Bounded readiness error code, if any.", "有限集合的就緒錯誤代碼；沒有時為 null。", "定義済みの readiness error code。ない場合は null。", "정의된 readiness error code이며 없으면 null."),
    "TTSCloneStatus.operator_hint": _text("Operator recovery command, if needed.", "需要時供操作者採取的復原指令。", "必要な場合の operator recovery command。", "필요한 경우 operator 복구 명령."),
    "TTSReferenceAssessment.duration_seconds": _text("Reference duration in seconds.", "參考錄音長度（秒）。", "参照音声の長さ（秒）。", "참조 음성 길이(초)."),
    "TTSReferenceAssessment.rms": _text("Reference root mean square level.", "參考錄音的均方根能量。", "参照音声の RMS level。", "참조 음성 RMS level."),
    "TTSReferenceAssessment.peak": _text("Reference peak amplitude.", "參考錄音的峰值振幅。", "参照音声の peak amplitude。", "참조 음성 peak amplitude."),
    "TTSReferenceAssessment.voiced_ratio": _text("Ratio of voiced 20 ms frames.", "20 ms 音框中偵測到聲音的比例。", "発話が検出された 20 ms frame の比率。", "음성이 감지된 20 ms frame 비율."),
    "TTSReferenceAssessment.quality": _text("Bounded reference quality result.", "有限集合的參考錄音品質結果。", "定義済みの参照音声 quality result。", "정의된 참조 음성 quality result."),
}


FORM_FIELD_TEXT = {
    "text": _text("UTF-8 text to synthesize, up to 20,000 characters.", "要合成的 UTF-8 文字，最多 20,000 個字元。", "合成する UTF-8 テキスト。最大 20,000 文字。", "합성할 UTF-8 텍스트, 최대 20,000자."),
    "style_cues": _text("Allowlisted best-effort style cue identifiers.", "allowlist 內的 best-effort 語氣提示識別碼。", "allowlist 内の best-effort style cue ID。", "allowlist 내 best-effort style cue ID."),
    "use_clone": _text("Use the supplied transient voice reference.", "是否使用隨請求提供的暫時參考錄音。", "request に含まれる一時的な参照音声を使用するか。", "요청에 포함된 임시 참조 음성을 사용할지 여부."),
    "reference": _text("Optional transient 5–30 second PCM WAV reference.", "選填的暫時性 5–30 秒 PCM WAV 參考錄音。", "任意の一時的な 5～30 秒 PCM WAV 参照音声。", "선택적 임시 5~30초 PCM WAV 참조 음성."),
}


PARAMETER_TEXT = {
    "verbose": _text("Include extended health detail when supported.", "在支援時包含延伸健康資訊。", "対応している場合に詳細な health 情報を含めます。", "지원되는 경우 확장 health 정보를 포함합니다."),
    "session_id": _text("Conversation session identifier.", "對話工作階段識別碼。", "会話 session ID。", "대화 session ID."),
    "speech_language": _text(
        "Speech language frozen for the session: auto, en, zh-TW, ja, or ko. Defaults to zh-TW.",
        "工作階段固定的語音語言：auto、en、zh-TW、ja 或 ko；預設為 zh-TW。",
        "session に固定する音声言語：auto、en、zh-TW、ja、ko。既定値は zh-TW。",
        "session에 고정할 음성 언어: auto, en, zh-TW, ja, ko. 기본값은 zh-TW입니다.",
    ),
    "asr_model": _text(
        "ASR model frozen for the session. Defaults to qwen3-asr-1.7b.",
        "工作階段固定的 ASR 模型；預設為 qwen3-asr-1.7b。",
        "session に固定する ASR model。既定値は qwen3-asr-1.7b。",
        "session에 고정할 ASR model. 기본값은 qwen3-asr-1.7b입니다.",
    ),
    "correction_model": _text(
        "Correction policy frozen for the session: qwen2.5-correction or disabled.",
        "工作階段固定的校正策略：qwen2.5-correction 或 disabled。",
        "session に固定する補正 policy：qwen2.5-correction または disabled。",
        "session에 고정할 교정 policy: qwen2.5-correction 또는 disabled.",
    ),
    "speaker_id": _text("Speaker record identifier.", "說話者資料識別碼。", "話者データ ID。", "화자 데이터 ID."),
    "name": _text("WAV artifact filename returned by TTS.", "TTS 回傳的 WAV 成品檔名。", "TTS が返した WAV 成果物 filename。", "TTS가 반환한 WAV 결과물 filename."),
}


WAV_TEXT = {
    "request": _text(
        "Upload one PCM WAV audio file. Content-Type must be audio/wav; maximum size is 8 MiB and maximum duration is 30 seconds unless configured otherwise.",
        "上傳單一 PCM WAV 音訊檔。Content-Type 必須是 audio/wav；大小最多 8 MiB、長度最多 30 秒（實際限制可由服務設定調整）。",
        "PCM WAV 音声ファイルを 1 つ upload します。Content-Type は audio/wav、最大 8 MiB、最大 30 秒です（service 設定で変更可能）。",
        "PCM WAV 오디오 파일 하나를 upload합니다. Content-Type은 audio/wav이며 최대 8 MiB, 최대 30초입니다(서비스 설정으로 변경 가능).",
    ),
    "binary": _text(
        "16-bit PCM WAV binary content; mono is recommended. Maximum 8 MiB and 30 seconds.",
        "16-bit PCM WAV 二進位內容；建議單聲道。上限 8 MiB、30 秒。",
        "16-bit PCM WAV binary。mono 推奨。上限 8 MiB、30 秒。",
        "16-bit PCM WAV binary이며 mono 권장. 최대 8 MiB, 30초.",
    ),
}


def localize_openapi(schema: dict[str, Any], locale: str | None) -> dict[str, Any]:
    language = normalize_locale(locale)
    localized = deepcopy(schema)
    localized["info"]["description"] = API_INFO["description"][language]
    localized["tags"] = [
        {
            "name": TAG_TEXT[key]["name"][language],
            "description": TAG_TEXT[key]["description"][language],
        }
        for key in TAG_KEYS
    ]

    for operation_key, translations in OPERATION_TEXT.items():
        method, path = operation_key.split(" ", 1)
        operation = localized["paths"][path][method.lower()]
        summary, description = translations[language].split("|", 1)
        operation["summary"] = summary
        operation["description"] = description
        tag_key = OPERATION_TAGS[operation_key]
        operation["tags"] = [TAG_TEXT[tag_key]["name"][language]]
        for parameter in operation.get("parameters", []):
            translated = PARAMETER_TEXT.get(parameter.get("name"))
            if translated:
                parameter["description"] = translated[language]
        request_body = operation.get("requestBody", {})
        wav_content = request_body.get("content", {}).get("audio/wav")
        if wav_content:
            request_body["description"] = WAV_TEXT["request"][language]
            wav_content["schema"]["description"] = WAV_TEXT["binary"][language]
        schema_reference = request_body.get("content", {}).get("multipart/form-data", {}).get("schema", {}).get("$ref")
        if schema_reference:
            schema_name = schema_reference.rsplit("/", 1)[-1]
            component = localized.get("components", {}).get("schemas", {}).get(schema_name, {})
            for field_name, field in component.get("properties", {}).items():
                translated = FORM_FIELD_TEXT.get(field_name)
                if translated:
                    field["description"] = translated[language]

    for field_key, translations in FIELD_TEXT.items():
        schema_name, field_name = field_key.split(".", 1)
        component = localized.get("components", {}).get("schemas", {}).get(schema_name)
        if component and field_name in component.get("properties", {}):
            component["properties"][field_name]["description"] = translations[language]

    return localized


def validate_catalogs() -> None:
    expected_operations = set(OPERATION_TAGS)
    if set(OPERATION_TEXT) != expected_operations:
        raise RuntimeError("OpenAPI operation locale catalog is incomplete")
    for translations in OPERATION_TEXT.values():
        if set(translations) != set(SUPPORTED_LOCALES) or any("|" not in value for value in translations.values()):
            raise RuntimeError("OpenAPI operation translation is incomplete")
    for translations in FIELD_TEXT.values():
        if set(translations) != set(SUPPORTED_LOCALES) or any(not value for value in translations.values()):
            raise RuntimeError("OpenAPI field translation is incomplete")


validate_catalogs()
