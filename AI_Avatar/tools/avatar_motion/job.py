from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path


SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _safe_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError(f"safe identifier required: {value!r}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(root: Path, path: Path) -> str:
    return os.path.relpath(path.resolve(), root.resolve())


def _resolve(root: Path, value: str) -> Path:
    return (root / value).resolve()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


@dataclass(frozen=True)
class Approval:
    pose_id: str
    candidate_path: str
    candidate_sha256: str
    prompt_path: str
    prompt_sha256: str
    reference_sha256: str
    s0_sha256: str
    rig_sha256: str
    motion_sha256: str
    automatic_gates: str
    human_decision: str


class MotionJobStore:
    def __init__(self, job_path: Path) -> None:
        self.job_path = job_path.resolve()
        self.root = self.job_path.parent

    @classmethod
    def load(cls, job_path: Path) -> "MotionJobStore":
        store = cls(job_path)
        store._job_payload()
        return store

    def _job_payload(self) -> dict:
        try:
            payload = json.loads(self.job_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot read motion job: {self.job_path}") from error
        if payload.get("version") != "1.0":
            raise ValueError("unsupported motion job version")
        return payload

    def _approval_payloads(self) -> list[dict]:
        path = self.root / "approvals.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("approvals must be an array")
        return payload

    def _current_input_hashes(self) -> dict[str, str]:
        payload = self._job_payload()
        return {
            name: _sha256(_resolve(self.root, item["path"]))
            for name, item in payload["inputs"].items()
        }

    def resolve_input(self, name: str) -> Path:
        payload = self._job_payload()
        return _resolve(self.root, payload["inputs"][name]["path"])

    def valid_approvals(self) -> tuple[Approval, ...]:
        payload = self._job_payload()
        current = self._current_input_hashes()
        expected_inputs = {
            name: item["sha256"] for name, item in payload["inputs"].items()
        }
        if current != expected_inputs:
            return ()
        valid: list[Approval] = []
        for index, raw in enumerate(self._approval_payloads()):
            if index >= len(payload["pose_ids"]):
                break
            approval = Approval(**raw)
            if approval.pose_id != payload["pose_ids"][index]:
                break
            if (
                approval.reference_sha256 != current["reference"]
                or approval.s0_sha256 != current["s0"]
                or approval.rig_sha256 != current["rig"]
                or approval.motion_sha256 != current["motion"]
                or approval.automatic_gates != "passed"
                or approval.human_decision != "approved"
            ):
                break
            candidate = _resolve(self.root, approval.candidate_path)
            prompt = _resolve(self.root, approval.prompt_path)
            if (
                not candidate.is_file()
                or not prompt.is_file()
                or _sha256(candidate) != approval.candidate_sha256
                or _sha256(prompt) != approval.prompt_sha256
            ):
                break
            valid.append(approval)
        return tuple(valid)

    @property
    def unlocked_pose_id(self) -> str | None:
        payload = self._job_payload()
        approvals = self.valid_approvals()
        if len(approvals) >= len(payload["pose_ids"]):
            return None
        return str(payload["pose_ids"][len(approvals)])

    def approve_pose(
        self,
        pose_id: str,
        *,
        candidate_path: Path,
        prompt_path: Path,
        automatic_gates: str,
        human_decision: str,
    ) -> Approval | None:
        if pose_id != self.unlocked_pose_id:
            raise ValueError(f"pose is not unlocked: {pose_id}")
        if automatic_gates != "passed" and human_decision == "approved":
            raise ValueError("automatic gates must pass before human approval")
        if human_decision not in {"approved", "rejected"}:
            raise ValueError("human decision must be approved or rejected")
        if human_decision == "rejected":
            return None
        current = self._current_input_hashes()
        approval = Approval(
            pose_id=pose_id,
            candidate_path=_relative(self.root, candidate_path),
            candidate_sha256=_sha256(candidate_path),
            prompt_path=_relative(self.root, prompt_path),
            prompt_sha256=_sha256(prompt_path),
            reference_sha256=current["reference"],
            s0_sha256=current["s0"],
            rig_sha256=current["rig"],
            motion_sha256=current["motion"],
            automatic_gates=automatic_gates,
            human_decision=human_decision,
        )
        approvals = [asdict(item) for item in self.valid_approvals()]
        approvals.append(asdict(approval))
        _write_json(self.root / "approvals.json", approvals)
        return approval


def init_job(
    *,
    candidate_root: Path,
    character_id: str,
    motion_id: str,
    job_id: str,
    reference_path: Path,
    s0_path: Path,
    rig_path: Path,
    motion_path: Path,
    pose_ids: tuple[str, ...],
) -> MotionJobStore:
    character_id = _safe_id(character_id)
    motion_id = _safe_id(motion_id)
    job_id = _safe_id(job_id)
    if not pose_ids:
        raise ValueError("motion job requires at least one generated pose")
    normalized_pose_ids = tuple(_safe_id(value) for value in pose_ids)
    if len(set(normalized_pose_ids)) != len(normalized_pose_ids):
        raise ValueError("generated pose IDs must be unique")
    inputs = {
        "reference": reference_path.resolve(),
        "s0": s0_path.resolve(),
        "rig": rig_path.resolve(),
        "motion": motion_path.resolve(),
    }
    for name, path in inputs.items():
        if not path.is_file():
            raise ValueError(f"missing {name} input: {path}")
    root = (
        candidate_root.resolve()
        / "gpt_image"
        / character_id
        / motion_id
        / job_id
    )
    root.mkdir(parents=True, exist_ok=False)
    payload = {
        "version": "1.0",
        "character_id": character_id,
        "motion_id": motion_id,
        "job_id": job_id,
        "pose_ids": list(normalized_pose_ids),
        "inputs": {
            name: {
                "path": _relative(root, path),
                "sha256": _sha256(path),
            }
            for name, path in inputs.items()
        },
    }
    job_path = root / "job.json"
    _write_json(job_path, payload)
    _write_json(root / "approvals.json", [])
    return MotionJobStore(job_path)

