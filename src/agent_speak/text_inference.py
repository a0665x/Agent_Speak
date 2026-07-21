"""Guarded llama.cpp client for endpoint decisions and transcript correction."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from .errors import PlatformError
from .realtime_models import CorrectionRevision
from .schemas import StrictModel
from .speech_languages import DEFAULT_SPEECH_LANGUAGE, SpeechLanguage


ENDPOINT_SYSTEM_PROMPTS: dict[SpeechLanguage, str] = {
    "auto": "Decide only whether this multilingual ASR utterance is complete. Do not answer it. Return only the specified JSON.",
    "en": "Decide only whether this English ASR utterance is complete. Do not answer it. Return only the specified JSON.",
    "zh-TW": "你只判斷繁體中文 ASR 語句是否已完整結束。不得回答內容。只輸出指定 JSON。",
    "ja": "日本語 ASR 発話が完結したかだけを判定してください。内容には回答せず、指定された JSON だけを出力してください。",
    "ko": "한국어 ASR 발화가 완결되었는지만 판단하세요. 내용에 답하지 말고 지정된 JSON만 출력하세요.",
}
REVISION_SYSTEM_PROMPTS: dict[SpeechLanguage, str] = {
    "auto": "You are a conservative multilingual realtime ASR corrector. Fix only recognition errors, spacing, and punctuation. Do not answer, summarize, add facts, or rewrite uncertain names, numbers, English tokens, URLs, or code. Return only the specified JSON.",
    "en": "You are a realtime English ASR corrector. Fix only spelling, spacing, punctuation, and sentence boundaries. Do not answer, summarize, add facts, or rewrite uncertain names, numbers, URLs, or code. Return only the specified JSON.",
    "zh-TW": "你是繁體中文即時 ASR 校正器，輸出必須使用繁體中文。只可修正錯字、斷詞與標點；不得回答、摘要、補充事實或改寫不確定的名稱、數字、英文、網址與程式碼。只輸出指定 JSON。",
    "ja": "日本語の realtime ASR 校正器です。かな・漢字の認識、分かち、句読点だけを修正してください。回答、要約、事実の追加、不確かな固有名詞・数字・URL・コードの改変は禁止です。指定された JSON だけを出力してください。",
    "ko": "한국어 realtime ASR 교정기입니다. 맞춤법, 띄어쓰기, 문장 부호만 교정하세요. 답변, 요약, 사실 추가, 불확실한 이름·숫자·URL·코드 변경은 금지합니다. 지정된 JSON만 출력하세요.",
}
CONTINUATION_MARKERS: dict[SpeechLanguage, tuple[str, ...]] = {
    "auto": (
        "because", "so", "but", "and", "if", "then",
        "因為", "所以", "但是", "然後", "如果", "以及",
        "ので", "から", "でも", "そして", "もし", "また",
        "때문에", "그래서", "하지만", "그리고", "만약", "또한",
    ),
    "en": ("because", "so", "but", "and", "if", "then"),
    "zh-TW": ("因為", "所以", "但是", "然後", "如果", "以及"),
    "ja": ("ので", "から", "でも", "そして", "もし", "また"),
    "ko": ("때문에", "그래서", "하지만", "그리고", "만약", "또한"),
}
PROTECTED_TOKEN = re.compile(
    r"https?://[^\s]+|`[^`]+`|\d+(?:\.\d+)+|[A-Za-z][A-Za-z0-9_+.-]*|\d+(?:\.\d+)?"
)


class _EndpointResult(StrictModel):
    complete: bool
    reason: str


class _RevisionResult(StrictModel):
    previous_text: str
    current_text: str
    changed: bool


class LlamaCppTextProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        request: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        max_edit_ratio: float = 0.35,
        device: str = "cpu",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.device = device
        self.max_edit_ratio = max_edit_ratio
        self._injected_request = request
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=2.0)
        )

    def detect(
        self,
        text: str,
        speech_language: SpeechLanguage = DEFAULT_SPEECH_LANGUAGE,
    ) -> tuple[bool, str]:
        payload = self._payload(
            ENDPOINT_SYSTEM_PROMPTS[speech_language],
            text,
            "endpoint_decision",
            {
                "type": "object",
                "properties": {
                    "complete": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["complete", "reason"],
                "additionalProperties": False,
            },
        )
        try:
            result = _EndpointResult.model_validate(self._content(self._request(payload)))
        except (IndexError, KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
            return (not ends_with_continuation(text, speech_language), "provider_invalid")
        return result.complete, result.reason

    def revise(
        self,
        previous_text: str,
        current_text: str,
        speech_language: SpeechLanguage = DEFAULT_SPEECH_LANGUAGE,
    ) -> CorrectionRevision:
        source = CorrectionRevision(previous_text, current_text, False)
        payload = self._payload(
            REVISION_SYSTEM_PROMPTS[speech_language],
            json.dumps(
                {"previous_text": previous_text, "current_text": current_text},
                ensure_ascii=False,
            ),
            "transcript_revision",
            {
                "type": "object",
                "properties": {
                    "previous_text": {"type": "string"},
                    "current_text": {"type": "string"},
                    "changed": {"type": "boolean"},
                },
                "required": ["previous_text", "current_text", "changed"],
                "additionalProperties": False,
            },
        )
        try:
            result = _RevisionResult.model_validate(self._content(self._request(payload)))
        except (IndexError, KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError):
            return source
        if not self._safe_revision(previous_text, current_text, result):
            return source
        return CorrectionRevision(result.previous_text, result.current_text, result.changed)

    def correct(self, text: str) -> str:
        return self.revise("", text).current_text

    def is_ready(self) -> bool:
        if self._injected_request is not None:
            return True
        try:
            response = self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._injected_request is not None:
            return self._injected_request(payload)
        try:
            response = self._client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PlatformError(
                "text_worker_unavailable",
                "Text inference worker is unavailable",
                status_code=503,
                stage="correction",
                retryable=True,
            ) from exc
        if not isinstance(result, dict):
            raise PlatformError(
                "invalid_text_worker_response",
                "Text inference worker returned invalid JSON",
                status_code=502,
                stage="correction",
                retryable=True,
            )
        return result

    def _payload(
        self,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 256,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }

    @staticmethod
    def _content(response: dict[str, Any]) -> dict[str, Any]:
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("message content must be JSON text")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise TypeError("message content must be a JSON object")
        return parsed

    def _safe_revision(
        self,
        previous_text: str,
        current_text: str,
        result: _RevisionResult,
    ) -> bool:
        source = previous_text + "\n" + current_text
        revised = result.previous_text + "\n" + result.current_text
        source_tokens = Counter(PROTECTED_TOKEN.findall(source))
        revised_tokens = Counter(PROTECTED_TOKEN.findall(revised))
        if any(revised_tokens[token] < count for token, count in source_tokens.items()):
            return False
        return _normalized_edit_distance(source, revised) <= self.max_edit_ratio


def _normalized_edit_distance(left: str, right: str) -> float:
    if left == right:
        return 0.0
    if not left or not right:
        return 1.0
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1] / max(len(left), len(right))


def ends_with_continuation(text: str, speech_language: SpeechLanguage) -> bool:
    stripped = text.rstrip()
    markers = CONTINUATION_MARKERS[speech_language]
    if speech_language in {"en", "auto"}:
        english = CONTINUATION_MARKERS["en"]
        if re.search(rf"(?:^|\s)({'|'.join(english)})$", stripped, flags=re.IGNORECASE):
            return True
        markers = tuple(marker for marker in markers if marker not in english)
    return stripped.endswith(markers)
