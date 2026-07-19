"""Stable transport models shared by routes and pipeline code."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(StrictModel):
    code: str = Field(description="穩定的機器可讀錯誤代碼", examples=["unsupported_media_type"])
    message: str = Field(description="可供使用者閱讀的錯誤訊息", examples=["Content-Type must be audio/wav"])
    stage: str | None = Field(default=None, description="發生錯誤的處理階段；不適用時為 null", examples=["vad"])
    retryable: bool = Field(default=False, description="相同輸入是否適合稍後重試", examples=[False])
    details: dict[str, Any] = Field(default_factory=dict, description="額外的結構化錯誤細節", examples=[{}])


class ErrorEnvelope(StrictModel):
    error: ErrorBody = Field(description="統一錯誤內容")


class ProviderCapability(StrictModel):
    stage: Literal["vad", "asr", "correction", "endpoint", "agent", "tts"] = Field(description="語音流程階段", examples=["asr"])
    name: str = Field(description="目前使用的提供者名稱", examples=["deterministic-development-asr"])
    ready: bool = Field(description="提供者是否可呼叫", examples=[True])
    development: bool = Field(description="是否為功能受限的開發版提供者", examples=[True])
    limitations: list[str] = Field(default_factory=list, description="已知限制", examples=[["Returns deterministic development text."]])
    version: str = Field(default="builtin", description="提供者版本", examples=["builtin"])
    device: str = Field(default="cpu", description="執行裝置", examples=["cpu"])


class CapabilitiesResponse(StrictModel):
    providers: list[ProviderCapability] = Field(description="六個處理階段的實際提供者")
    speaker_matching_notice: str = Field(default="Convenience identification only; not biometric authentication.", description="說話者比對安全提醒", examples=["Convenience identification only; not biometric authentication."])


class HealthResponse(StrictModel):
    status: Literal["ok"] = Field(default="ok", description="服務健康狀態", examples=["ok"])
    version: str = Field(description="Agent Speak 版本", examples=["0.1.0"])
    storage_ready: bool = Field(description="本機資料目錄是否就緒", examples=[True])


class PipelineEvent(StrictModel):
    sequence: int = Field(ge=1, description="工作階段內遞增的事件序號", examples=[1])
    type: str = Field(description="事件類型", examples=["pipeline.started"])
    stage: str | None = Field(default=None, description="相關處理階段", examples=["vad"])
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC 事件時間", examples=["2026-01-01T00:00:00Z"])
    elapsed_ms: float | None = Field(default=None, ge=0, description="階段耗時（毫秒）", examples=[12.4])
    data: dict[str, Any] = Field(default_factory=dict, description="事件附加資料", examples=[{}])


class SessionSummary(StrictModel):
    id: str = Field(description="工作階段識別碼", examples=["7f0e1a2b3c4d"])
    state: str = Field(description="工作階段狀態", examples=["ready"])
    created_at: datetime = Field(description="UTC 建立時間", examples=["2026-01-01T00:00:00Z"])
    events: list[PipelineEvent] = Field(default_factory=list, description="目前保留的流程事件")


class TextInput(StrictModel):
    text: str = Field(min_length=1, max_length=20_000, description="要處理的 UTF-8 文字，不可為空，最多 20,000 個字元", examples=["請幫我整理今天的工作重點"])


class TextOutput(StrictModel):
    text: str = Field(description="處理後的文字結果", examples=["今天的工作重點已整理完成。"])


class EndDetectOutput(StrictModel):
    complete: bool = Field(description="是否判定使用者已說完", examples=[True])
    reason: str = Field(description="判定原因", examples=["terminal_punctuation"])


class VadOutput(StrictModel):
    voiced: bool = Field(description="音訊中是否偵測到人聲", examples=[True])
    rms: float = Field(ge=0, description="音訊均方根能量", examples=[0.12])
    duration_seconds: float = Field(ge=0, description="音訊長度（秒）", examples=[2.4])


class TtsOutput(StrictModel):
    audio_url: str = Field(description="可取得合成 WAV 的站內網址", examples=["/api/v1/artifacts/response-abc.wav"])
    content_type: Literal["audio/wav"] = Field(default="audio/wav", description="音訊 MIME 類型", examples=["audio/wav"])


class TurnResponse(StrictModel):
    transcript: str = Field(description="ASR 原始辨識文字", examples=["請幫我整理今天工作重點"])
    corrected_text: str = Field(description="校正後文字", examples=["請幫我整理今天的工作重點。"])
    end_detected: bool = Field(description="是否判定語句結束", examples=[True])
    endpoint_reason: str = Field(description="語句結束判定原因", examples=["terminal_punctuation"])
    response: str = Field(description="Agent 文字回覆", examples=["好的，我會協助整理工作重點。"])
    audio_url: str = Field(description="Agent 回覆的 WAV 站內網址", examples=["/api/v1/artifacts/response-abc.wav"])
    latencies_ms: dict[str, float] = Field(description="各處理階段耗時（毫秒）", examples=[{"vad": 1.2, "asr": 4.5, "agent": 2.1}])


SPEAKER_NOTICE = "Convenience identification only; this is not biometric authentication."


class SpeakerCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100, description="說話者顯示名稱，1 至 100 字元", examples=["小明"])
    notes: str = Field(default="", max_length=500, description="選填備註，最多 500 字元", examples=["會議室麥克風"])


class SpeakerUpdate(StrictModel):
    name: str = Field(min_length=1, max_length=100, description="更新後的顯示名稱", examples=["小明"])
    notes: str = Field(default="", max_length=500, description="更新後的選填備註", examples=[""])


class SpeakerProfile(StrictModel):
    id: str = Field(description="說話者資料識別碼", examples=["spk_abc123"])
    name: str = Field(description="顯示名稱", examples=["小明"])
    notes: str = Field(description="備註", examples=["會議室麥克風"])
    created_at: datetime = Field(description="UTC 建立時間", examples=["2026-01-01T00:00:00Z"])
    sample_count: int = Field(ge=0, description="已登錄樣本數", examples=[2])


class SpeakerEnvelope(StrictModel):
    speaker: SpeakerProfile = Field(description="說話者資料")
    notice: str = Field(default=SPEAKER_NOTICE, description="便利識別而非身分驗證的提醒", examples=[SPEAKER_NOTICE])


class SpeakerList(StrictModel):
    speakers: list[SpeakerProfile] = Field(description="本機說話者資料清單")
    notice: str = Field(default=SPEAKER_NOTICE, description="便利識別而非身分驗證的提醒", examples=[SPEAKER_NOTICE])


class SpeakerMatch(StrictModel):
    match: SpeakerProfile | None = Field(description="最接近且達門檻的資料；無結果時為 null")
    score: float | None = Field(description="相似分數；無結果時為 null", examples=[0.87])
    threshold: float = Field(description="本次使用的比對門檻", examples=[0.8])


class SpeakerMatchEnvelope(SpeakerMatch):
    notice: str = Field(default=SPEAKER_NOTICE, description="便利識別而非身分驗證的提醒", examples=[SPEAKER_NOTICE])
