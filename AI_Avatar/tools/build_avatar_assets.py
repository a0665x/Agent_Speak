from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .avatar_assets.builder import (
    ExtractionResult,
    extract_inventory,
    publish_candidates,
    review_candidate_loops,
    write_contact_sheet,
)
from .avatar_assets.interpolation import build_routed_interpolator
from .avatar_assets.manifest import load_manifest, validate_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = PROJECT_ROOT / "AI_Avatar/config/verified_asset_inventory.json"
DEFAULT_SHEETS = PROJECT_ROOT / "AI_Avatar/assets/sheets"
DEFAULT_CANDIDATES = PROJECT_ROOT / "AI_Avatar/.candidates"
DEFAULT_PUBLIC = PROJECT_ROOT / "AI_Avatar/public"
DEFAULT_PROVIDERS = PROJECT_ROOT / "AI_Avatar/config/interpolation_providers.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, build, review, and publish Henry avatar assets."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser(
        "inspect",
        help="Extract a review contact sheet from the verified inventory.",
    )
    inspect.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    inspect.add_argument("--sheets", type=Path, default=DEFAULT_SHEETS)
    inspect.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    inspect.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "runtime/avatar-review/contact-sheet.png",
    )
    inspect.add_argument("--reference-width", type=int, default=380)
    inspect.add_argument("--reference-height", type=int, default=360)
    inspect.add_argument("--background-tolerance", type=int, default=18)
    extract = subparsers.add_parser(
        "extract",
        help="Crop and normalize reviewed source frames.",
    )
    extract.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    extract.add_argument("--sheets", type=Path, default=DEFAULT_SHEETS)
    extract.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    extract.add_argument("--reference-width", type=int, default=380)
    extract.add_argument("--reference-height", type=int, default=360)
    extract.add_argument("--background-tolerance", type=int, default=18)
    review = subparsers.add_parser(
        "review",
        help="Build candidate loops and visual previews.",
    )
    review.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    review.add_argument("--provider", choices=("none", "auto", "film", "rife"), default="auto")
    review.add_argument("--providers-config", type=Path, default=DEFAULT_PROVIDERS)
    publish = subparsers.add_parser(
        "publish",
        help="Publish six clips against reviewed report hashes.",
    )
    publish.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    publish.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    publish.add_argument("--approve", action="append", default=[])
    validate = subparsers.add_parser(
        "validate",
        help="Validate a published runtime manifest.",
    )
    validate.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    return parser


def _load_extraction(candidate_root: Path) -> ExtractionResult:
    states = {}
    for state in ("idle", "listening", "thinking", "speaking", "happy", "error"):
        paths = tuple(sorted((candidate_root / "extracted" / state).glob("*.png")))
        if not paths:
            raise ValueError(f"missing extracted frames for {state}")
        states[state] = paths
    transition = candidate_root / "shared/henry_s0.png"
    if not transition.is_file():
        raise ValueError("missing extracted shared transition frame")
    return ExtractionResult(transition_frame=transition, states=states)


def _parse_approvals(values: Sequence[str]) -> dict[str, str]:
    approvals: dict[str, str] = {}
    for value in values:
        clip_id, separator, report_hash = value.partition(":")
        if (
            separator != ":"
            or not clip_id
            or len(report_hash) != 64
            or any(character not in "0123456789abcdef" for character in report_hash)
        ):
            raise ValueError(f"invalid approval: {value}")
        approvals[clip_id] = report_hash
    return approvals


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "inspect":
        extracted = extract_inventory(
            args.inventory,
            args.sheets,
            args.candidates,
            reference_width=args.reference_width,
            reference_height=args.reference_height,
            background_tolerance=args.background_tolerance,
        )
        count = write_contact_sheet(extracted, args.output)
        print(f"AVATAR_INVENTORY_READY entries={count} contact_sheet={args.output}")
        return 0
    if args.command == "extract":
        result = extract_inventory(
            args.inventory,
            args.sheets,
            args.candidates,
            reference_width=args.reference_width,
            reference_height=args.reference_height,
            background_tolerance=args.background_tolerance,
        )
        print(
            f"AVATAR_EXTRACTED states={len(result.states)} "
            f"candidates={args.candidates}"
        )
        return 0
    if args.command == "review":
        interpolator = (
            (lambda _start, _end, _phase: ())
            if args.provider == "none"
            else build_routed_interpolator(
                args.providers_config,
                project_root=PROJECT_ROOT,
                candidate_root=args.candidates,
                preferred=args.provider,
            )
        )
        result = review_candidate_loops(
            _load_extraction(args.candidates),
            args.candidates,
            interpolator=interpolator,
        )
        print(
            f"AVATAR_REVIEW_READY clips={len(result.report_hashes)} "
            f"candidates={args.candidates}"
        )
        for clip_id, report_hash in result.report_hashes.items():
            print(f"APPROVE --approve {clip_id}:{report_hash}")
        return 0
    if args.command == "publish":
        result = publish_candidates(
            args.candidates,
            args.public,
            _parse_approvals(args.approve),
        )
        print(
            f"AVATAR_PUBLISHED clips={len(result.published)} "
            f"manifest={result.manifest_path}"
        )
        return 0
    if args.command == "validate":
        manifest = load_manifest(args.public / "manifest.json")
        validate_manifest(manifest, args.public)
        print(
            f"AVATAR_ASSETS_VALID clips={len(manifest.clips)} "
            f"transition={manifest.transition_frame_id}"
        )
        return 0
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
