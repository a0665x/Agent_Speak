"""Ordered transcript state with a one-sentence revision window."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import PlatformError
from .realtime_models import CorrectionRevision


def stable_prefix(previous: str, current: str) -> str:
    limit = min(len(previous), len(current))
    index = 0
    while index < limit and previous[index] == current[index]:
        index += 1
    return current[:index]


@dataclass(frozen=True, slots=True)
class TranscriptRow:
    utterance_id: str
    text: str
    final: bool
    locked: bool = False
    revisable: bool = False


class TranscriptLedger:
    def __init__(self) -> None:
        self._rows: list[TranscriptRow] = []

    def rows(self) -> tuple[TranscriptRow, ...]:
        return tuple(self._rows)

    def accept_partial(self, utterance_id: str, text: str) -> None:
        if not self._rows:
            self._rows.append(TranscriptRow(utterance_id, text, final=False))
            return
        current = self._rows[-1]
        if current.utterance_id == utterance_id and not current.locked:
            self._rows[-1] = replace(current, text=text)
            return
        if current.final and self._is_new(utterance_id):
            self._open_next(utterance_id, text, final=False)
            return
        self._raise_stale()

    def accept_final(self, utterance_id: str, text: str) -> None:
        if not self._rows:
            self._rows.append(TranscriptRow(utterance_id, text, final=True))
            return
        current = self._rows[-1]
        if current.utterance_id == utterance_id and not current.locked:
            self._rows[-1] = replace(current, text=text, final=True)
            return
        if current.final and self._is_new(utterance_id):
            self._open_next(utterance_id, text, final=True)
            return
        self._raise_stale()

    def apply_revision(self, current_utterance_id: str, result: CorrectionRevision) -> None:
        if not self._rows or self._rows[-1].utterance_id != current_utterance_id:
            self._raise_stale()
        current = self._rows[-1]
        if current.locked or not current.final:
            self._raise_stale()
        if len(self._rows) > 1:
            previous = self._rows[-2]
            if previous.locked or not previous.revisable:
                self._raise_stale()
            self._rows[-2] = replace(
                previous,
                text=result.previous_text,
                locked=True,
                revisable=False,
            )
        self._rows[-1] = replace(current, text=result.current_text)

    def finalize(self) -> None:
        self._rows = [replace(row, locked=True, revisable=False) for row in self._rows]

    def _open_next(self, utterance_id: str, text: str, *, final: bool) -> None:
        current = self._rows[-1]
        if not current.locked:
            self._rows[-1] = replace(current, revisable=True)
        self._rows.append(TranscriptRow(utterance_id, text, final=final))

    def _is_new(self, utterance_id: str) -> bool:
        return all(row.utterance_id != utterance_id for row in self._rows)

    @staticmethod
    def _raise_stale() -> None:
        raise PlatformError(
            "stale_transcript",
            "Transcript update is stale",
            stage="correction",
            retryable=False,
        )
