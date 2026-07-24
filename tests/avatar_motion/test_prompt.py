from pathlib import Path

from AI_Avatar.tools.avatar_motion.prompt import build_prompt_packet


def test_prompt_packet_contains_three_ordered_images_and_invariants() -> None:
    packet = build_prompt_packet(
        canonical_reference=Path("reference.png"),
        current_pose_map=Path("pose.png"),
        nearest_approved_frame=Path("approved.png"),
        identity_invariants=("same glasses", "same badge"),
        geometry_invariants=("keep both feet on the locked baseline",),
        canvas=(512, 512),
        background="#00ff66",
    )

    assert [item.role for item in packet.images] == [
        "canonical_reference",
        "current_pose_map",
        "nearest_approved_frame",
    ]
    assert "keep both feet on the locked baseline" in packet.text
    assert packet.background == "#00ff66"
    assert packet.canvas == (512, 512)


def test_prompt_rejects_missing_reference_path() -> None:
    try:
        build_prompt_packet(
            canonical_reference=Path(""),
            current_pose_map=Path("pose.png"),
            nearest_approved_frame=Path("approved.png"),
            identity_invariants=(),
            geometry_invariants=(),
            canvas=(512, 512),
            background="#00ff66",
        )
    except ValueError as error:
        assert "reference" in str(error)
    else:
        raise AssertionError("missing reference path was accepted")

