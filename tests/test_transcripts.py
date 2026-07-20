import pytest

from agent_speak.errors import PlatformError
from agent_speak.realtime_models import CorrectionRevision
from agent_speak.transcripts import TranscriptLedger, stable_prefix


def test_stable_prefix_uses_consecutive_hypotheses() -> None:
    assert stable_prefix("我要去新竹", "我要去新竹科學園區") == "我要去新竹"


def test_only_previous_sentence_can_be_revised() -> None:
    ledger = TranscriptLedger()
    ledger.accept_final("u1", "第一句")
    ledger.accept_final("u2", "第二句")
    ledger.apply_revision("u2", CorrectionRevision("第一句已修正", "第二句已修正", True))
    ledger.accept_final("u3", "第三句")
    assert ledger.rows()[0].locked is True
    assert ledger.rows()[0].text == "第一句已修正"
    assert ledger.rows()[1].revisable is True
    assert ledger.rows()[1].text == "第二句已修正"


def test_partial_can_only_update_the_open_utterance() -> None:
    ledger = TranscriptLedger()
    ledger.accept_partial("u1", "你")
    ledger.accept_partial("u1", "你好")
    ledger.accept_final("u1", "你好。")
    ledger.accept_partial("u2", "下一句")
    assert [row.text for row in ledger.rows()] == ["你好。", "下一句"]

    with pytest.raises(PlatformError, match="stale"):
        ledger.accept_partial("u1", "不應覆寫")


def test_stale_revision_never_mutates_another_sentence() -> None:
    ledger = TranscriptLedger()
    ledger.accept_final("u1", "第一句")
    ledger.accept_final("u2", "第二句")
    before = ledger.rows()
    with pytest.raises(PlatformError, match="stale"):
        ledger.apply_revision("missing", CorrectionRevision("錯", "錯", True))
    assert ledger.rows() == before


def test_finalize_locks_the_last_row() -> None:
    ledger = TranscriptLedger()
    ledger.accept_final("u1", "完成")
    ledger.finalize()
    assert ledger.rows()[0].locked is True
    assert ledger.rows()[0].revisable is False
