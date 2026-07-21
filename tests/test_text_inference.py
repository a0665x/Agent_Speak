import json

import pytest

from agent_speak.config import Settings
from agent_speak.pipeline import ProviderSet
from agent_speak.text_inference import LlamaCppTextProvider


def response(content: dict[str, object]) -> dict[str, object]:
    return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}


def test_endpoint_uses_strict_json_and_preserves_reason() -> None:
    payloads: list[dict[str, object]] = []
    provider = LlamaCppTextProvider(
        "http://worker:8080",
        "qwen",
        request=lambda payload: (
            payloads.append(payload) or response({"complete": False, "reason": "continuation"})
        ),
    )
    assert provider.detect("因為") == (False, "continuation")
    assert payloads[0]["temperature"] == 0
    assert payloads[0]["response_format"]["type"] == "json_schema"  # type: ignore[index]


def test_revision_preserves_numbers_english_and_code_tokens() -> None:
    provider = LlamaCppTextProvider(
        "http://worker:8080",
        "qwen",
        request=lambda _: response(
            {
                "previous_text": "Python 3.11 使用 CUDA",
                "current_text": "延遲 900 ms",
                "changed": True,
            }
        ),
    )
    result = provider.revise("Python 3.11 使用 CUDA", "延遲 900 ms")
    assert result.current_text == "延遲 900 ms"


def test_excessive_or_protected_token_edit_falls_back_to_source() -> None:
    provider = LlamaCppTextProvider(
        "http://worker:8080",
        "qwen",
        request=lambda _: response(
            {
                "previous_text": "刪除 Python 3.11",
                "current_text": "完全不同的新答案",
                "changed": True,
            }
        ),
    )
    result = provider.revise("保留 Python 3.11", "延遲 900 ms")
    assert result.previous_text == "保留 Python 3.11"
    assert result.current_text == "延遲 900 ms"
    assert result.changed is False


def test_invalid_worker_shape_falls_back_without_mutating_text() -> None:
    provider = LlamaCppTextProvider(
        "http://worker:8080",
        "qwen",
        request=lambda _: {"choices": []},
    )
    result = provider.revise("前句", "本句")
    assert (result.previous_text, result.current_text, result.changed) == ("前句", "本句", False)
    assert provider.detect("所以") == (False, "provider_invalid")


def test_correct_keeps_existing_provider_signature() -> None:
    provider = LlamaCppTextProvider(
        "http://worker:8080",
        "qwen",
        request=lambda _: response(
            {"previous_text": "", "current_text": "修正文字。", "changed": True}
        ),
    )
    assert provider.correct("修正文字") == "修正文字。"


def test_configured_provider_uses_one_text_worker_for_both_stages() -> None:
    settings = Settings(correction_worker_url="http://worker:8080")
    providers = ProviderSet.configured(settings, vad=object())
    assert isinstance(providers.correction, LlamaCppTextProvider)
    assert providers.endpoint is providers.correction


@pytest.mark.parametrize(
    ("speech_language", "expected_policy"),
    [
        ("auto", "multilingual"),
        ("en", "English"),
        ("zh-TW", "繁體中文"),
        ("ja", "日本語"),
        ("ko", "한국어"),
    ],
)
def test_endpoint_and_revision_prompts_follow_session_language(
    speech_language: str, expected_policy: str
) -> None:
    payloads: list[dict[str, object]] = []
    responses = iter(
        [
            response({"complete": True, "reason": "complete"}),
            response(
                {
                    "previous_text": "",
                    "current_text": "text",
                    "changed": False,
                }
            ),
        ]
    )
    provider = LlamaCppTextProvider(
        "http://worker:8080",
        "qwen",
        request=lambda payload: payloads.append(payload) or next(responses),
    )

    provider.detect("text", speech_language)  # type: ignore[arg-type]
    provider.revise("", "text", speech_language)  # type: ignore[arg-type]

    endpoint_prompt = payloads[0]["messages"][0]["content"]  # type: ignore[index]
    revision_prompt = payloads[1]["messages"][0]["content"]  # type: ignore[index]
    assert expected_policy in endpoint_prompt
    assert expected_policy in revision_prompt
    assert payloads[0]["temperature"] == 0
    assert payloads[1]["response_format"]["type"] == "json_schema"  # type: ignore[index]


@pytest.mark.parametrize(
    ("speech_language", "text"),
    [
        ("en", "I stopped because"),
        ("zh-TW", "我停下來因為"),
        ("ja", "停止したので"),
        ("ko", "중지했기 때문에"),
        ("auto", "I stopped because"),
        ("auto", "我停下來因為"),
    ],
)
def test_language_specific_continuations_survive_invalid_worker_output(
    speech_language: str, text: str
) -> None:
    provider = LlamaCppTextProvider(
        "http://worker:8080",
        "qwen",
        request=lambda _: {"choices": []},
    )

    assert provider.detect(text, speech_language) == (False, "provider_invalid")  # type: ignore[arg-type]
