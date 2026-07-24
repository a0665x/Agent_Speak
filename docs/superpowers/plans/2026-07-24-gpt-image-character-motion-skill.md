# GPT Image Character Motion Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable project-local skill that turns a reviewed full-body character reference into a validated rig, deterministic pose maps, stage-gated GPT Image candidates, and one un-published Henry scratch-head proof loop.

**Architecture:** A Python candidate pipeline validates immutable JSON inputs, renders pose maps deterministically, requests one image at a time through a provider boundary, converts flat-chroma output to RGBA, and binds every human approval to input hashes. Generated media stays below ignored `AI_Avatar/.candidates/`; only the existing reviewed publisher may copy normalized PNG frames into runtime assets.

**Tech Stack:** Python 3.11, `jsonschema`, Pillow, NumPy, OpenCV, `httpx`, pytest, Codex project-local skills, GPT Image 2 Image API.

---

## File structure

Create focused files with these responsibilities:

- `AI_Avatar/assets/skills/generate-character-motion/SKILL.md`: Agent-facing workflow and safety boundary.
- `AI_Avatar/assets/skills/generate-character-motion/agents/openai.yaml`: Skill discovery metadata.
- `AI_Avatar/assets/skills/generate-character-motion/assets/*.schema.json`: strict rig, motion, and candidate-clip schemas.
- `AI_Avatar/assets/skills/generate-character-motion/assets/scratch-head.motion.json`: reusable choreography example.
- `AI_Avatar/assets/skills/generate-character-motion/references/*.md`: provider prompt and review contracts.
- `AI_Avatar/assets/skills/generate-character-motion/scripts/*.py`: thin CLI entry points that import tested project modules.
- `AI_Avatar/tools/avatar_motion/models.py`: immutable rig, motion, job, and approval models.
- `AI_Avatar/tools/avatar_motion/pose.py`: deterministic skeleton renderer.
- `AI_Avatar/tools/avatar_motion/job.py`: preflight, safe candidate paths, hashes, stage locking, and resume.
- `AI_Avatar/tools/avatar_motion/matte.py`: flat-chroma matte, despill, and edge validation.
- `AI_Avatar/tools/avatar_motion/prompt.py`: anchored-neighbor prompt packet.
- `AI_Avatar/tools/avatar_motion/provider.py`: provider protocol and opt-in GPT Image 2 adapter.
- `AI_Avatar/tools/avatar_motion/review.py`: automatic gates, contact sheets, and hash-bound approvals.
- `AI_Avatar/tools/build_avatar_motion.py`: operator CLI.
- `AI_Avatar/assets/gpt_image_assets/rigs/henry.rig.json`: reviewed Henry rig.
- `AI_Avatar/assets/gpt_image_assets/pose-maps/henry/scratch_head/*.png`: deterministic, reproducible pose maps.
- `tests/avatar_motion/*.py`: offline unit and integration tests.

Do not add generated flesh frames, provider responses, prompts containing private
data, model weights, or API keys to Git.

### Task 1: Candidate models and strict schemas

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/__init__.py`
- Create: `AI_Avatar/tools/avatar_motion/models.py`
- Create: `AI_Avatar/assets/skills/generate-character-motion/assets/rig.schema.json`
- Create: `AI_Avatar/assets/skills/generate-character-motion/assets/motion.schema.json`
- Create: `AI_Avatar/assets/skills/generate-character-motion/assets/candidate-clip.schema.json`
- Create: `AI_Avatar/assets/skills/generate-character-motion/assets/scratch-head.motion.json`
- Modify: `pyproject.toml`
- Test: `tests/avatar_motion/test_models.py`

- [ ] **Step 1: Write failing schema and model tests**

```python
def test_rig_supports_character_specific_extension_joints(tmp_path):
    rig = load_rig(write_json(tmp_path / "rig.json", valid_rig(
        joints={"ear_tip_left": {"x": 0.40, "y": 0.08}},
        bones=[["ear_root_left", "ear_tip_left"]],
    )))
    assert rig.joints["ear_tip_left"].x == 0.40


def test_motion_rejects_unknown_joint(tmp_path):
    with pytest.raises(ValueError, match="unknown joint"):
        load_motion(write_json(
            tmp_path / "motion.json",
            valid_motion(poses=[{"id": "lift", "joints": {"third_arm": [0.2, 0.3]}}]),
        ), valid_rig())


def test_candidate_contract_requires_exact_s0_hash_at_both_boundaries(tmp_path):
    with pytest.raises(ValueError, match="boundary"):
        load_candidate_clip(write_json(tmp_path / "clip.json", {
            **valid_candidate_clip(),
            "first_frame_sha256": "a" * 64,
            "last_frame_sha256": "b" * 64,
        }))
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_models.py
```

Expected: collection fails because `AI_Avatar.tools.avatar_motion.models` does
not exist.

- [ ] **Step 3: Implement immutable models and schema loaders**

Define `Point`, `Rig`, `Pose`, `Motion`, and `CandidateClip` as frozen
dataclasses. Implement:

```python
def load_rig(path: Path) -> Rig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload(payload, RIG_SCHEMA)
    return Rig.from_payload(payload)


def load_motion(path: Path, rig: Rig) -> Motion:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload(payload, MOTION_SCHEMA)
    return Motion.from_payload(payload, rig)


def load_candidate_clip(path: Path) -> CandidateClip:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload(payload, CANDIDATE_CLIP_SCHEMA)
    return CandidateClip.from_payload(payload)
```

Each loader must use Draft 2020-12 JSON Schema, reject additional properties,
reject unsafe IDs outside `^[a-z0-9][a-z0-9_-]{0,63}$`, require coordinates in
`[0, 1]`, reject bones that reference missing joints, reject motion poses that
reference missing joints, and require matching first/last S0 hashes.
Add `jsonschema>=4.23,<5` to both the `avatar` and `test` optional dependency
groups, and add `pytest-httpx>=0.35,<1` to `test`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest -q tests/avatar_motion/test_models.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml AI_Avatar/tools/avatar_motion AI_Avatar/assets/skills/generate-character-motion/assets tests/avatar_motion/test_models.py
git commit -m "feat: define avatar motion candidate contracts"
```

### Task 2: Deterministic rig and pose-map renderer

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/pose.py`
- Create: `AI_Avatar/assets/skills/generate-character-motion/scripts/render_pose_maps.py`
- Test: `tests/avatar_motion/test_pose.py`

- [ ] **Step 1: Write failing deterministic-render tests**

```python
def test_pose_renderer_is_byte_deterministic(tmp_path):
    first = render_pose_map(valid_rig(), valid_pose(), (512, 512))
    second = render_pose_map(valid_rig(), valid_pose(), (512, 512))
    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    save_png(first, first_path)
    save_png(second, second_path)
    assert first_path.read_bytes() == second_path.read_bytes()


def test_locked_feet_remain_at_rig_coordinates():
    image, resolved = render_pose_map_with_points(valid_rig(), valid_pose())
    assert resolved["foot_left"] == valid_rig().joints["foot_left"]
    assert resolved["foot_right"] == valid_rig().joints["foot_right"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_pose.py
```

Expected: import fails because `pose.py` does not exist.

- [ ] **Step 3: Implement the renderer**

Use Pillow only. Resolve each pose as `rig joints + allowed overrides`, ignore
no input silently, draw bones in declared order, draw joints after bones, and
save with fixed PNG options:

```python
def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=False, compress_level=9)
```

The CLI takes `--rig`, `--motion`, and `--output`, writes one PNG per pose, and
prints `POSE_MAPS_READY count=<n> output=<path>`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest -q tests/avatar_motion/test_pose.py
```

Expected: all tests pass and repeated output hashes match.

- [ ] **Step 5: Commit**

```bash
git add AI_Avatar/tools/avatar_motion/pose.py AI_Avatar/assets/skills/generate-character-motion/scripts/render_pose_maps.py tests/avatar_motion/test_pose.py
git commit -m "feat: render deterministic avatar pose maps"
```

### Task 3: Safe job initialization and approval state machine

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/job.py`
- Create: `AI_Avatar/assets/skills/generate-character-motion/scripts/init_motion_job.py`
- Test: `tests/avatar_motion/test_job.py`

- [ ] **Step 1: Write failing job safety tests**

```python
def test_job_root_stays_below_candidates(tmp_path):
    with pytest.raises(ValueError, match="safe identifier"):
        init_job(tmp_path, "../../escape", "scratch_head", inputs())


def test_only_first_pose_is_unlocked_initially(tmp_path):
    job = init_job(tmp_path, "henry", "scratch_head", inputs())
    assert job.unlocked_pose_id == "anticipation"


def test_approval_hash_change_invalidates_downstream(tmp_path):
    store = approved_three_stage_store(tmp_path)
    store.replace_input("motion_sha256", "f" * 64)
    assert store.valid_approvals() == ()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_job.py
```

Expected: import fails because `job.py` does not exist.

- [ ] **Step 3: Implement safe job creation and hash-bound resume**

Store only relative paths and SHA-256 values. `approve_pose()` must require:

```python
Approval(
    pose_id=pose_id,
    candidate_sha256=sha256(candidate),
    reference_sha256=job.reference_sha256,
    rig_sha256=job.rig_sha256,
    motion_sha256=job.motion_sha256,
    prompt_sha256=sha256(prompt_packet),
    automatic_gates="passed",
    human_decision="approved",
)
```

Reject approval if automatic gates did not pass. Unlock exactly the next pose.
On resume, invalidate the first mismatching approval and every downstream
approval.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest -q tests/avatar_motion/test_job.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add AI_Avatar/tools/avatar_motion/job.py AI_Avatar/assets/skills/generate-character-motion/scripts/init_motion_job.py tests/avatar_motion/test_job.py
git commit -m "feat: add hash-bound avatar motion jobs"
```

### Task 4: Chroma matte and automatic image gates

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/matte.py`
- Modify: `AI_Avatar/tools/avatar_motion/review.py`
- Test: `tests/avatar_motion/test_matte.py`
- Test: `tests/avatar_motion/test_motion_review.py`

- [ ] **Step 1: Write failing matte and gate tests**

```python
def test_chroma_matte_keeps_paw_tip_and_removes_green_corners():
    result = chroma_to_rgba(green_fixture_with_brown_character(), ChromaKey("#00ff66", 42, 2))
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((48, 12))[3] > 220
    assert result.getpixel((48, 12))[1] < 210


def test_review_rejects_detached_component_and_boundary_jump():
    report = review_candidate(candidate_with_detached_paw(), previous_s0(), thresholds())
    assert set(report.failed_rules) >= {"detached_component", "adjacent_delta"}
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_matte.py tests/avatar_motion/test_motion_review.py
```

Expected: imports fail because matte and review modules do not exist.

- [ ] **Step 3: Implement matte and reports**

Implement a border-connected chroma mask, one configurable feather radius,
despill only on semi-transparent edge pixels, largest-component checks, canvas
checks, foreground coverage, center/baseline drift, silhouette delta, and
identity-region bounding-box deltas. Always return `needs_review` after clean
automatic gates; never return automatic approval.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest -q tests/avatar_motion/test_matte.py tests/avatar_motion/test_motion_review.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add AI_Avatar/tools/avatar_motion/matte.py AI_Avatar/tools/avatar_motion/review.py tests/avatar_motion/test_matte.py tests/avatar_motion/test_motion_review.py
git commit -m "feat: gate avatar mattes and temporal geometry"
```

### Task 5: Anchored-neighbor prompt and GPT Image provider boundary

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/prompt.py`
- Create: `AI_Avatar/tools/avatar_motion/provider.py`
- Create: `AI_Avatar/assets/skills/generate-character-motion/references/prompt-contract.md`
- Test: `tests/avatar_motion/test_prompt.py`
- Test: `tests/avatar_motion/test_provider.py`

- [ ] **Step 1: Write failing prompt/provider tests**

```python
def test_prompt_packet_contains_three_ordered_images_and_invariants():
    packet = build_prompt_packet(job(), pose_id="scratch_contact")
    assert [item.role for item in packet.images] == [
        "canonical_reference", "current_pose_map", "nearest_approved_frame"
    ]
    assert "keep both feet on the locked baseline" in packet.text
    assert packet.background == "#00ff66"


def test_provider_never_serializes_api_key(httpx_mock, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    httpx_mock.add_response(json={"data": [{"b64_json": base64_png()}]})
    result = GptImageProvider().edit(packet(), tmp_path / "opaque.png")
    assert result.output_path.is_file()
    assert "secret-value" not in json.dumps(result.safe_metadata)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_prompt.py tests/avatar_motion/test_provider.py
```

Expected: imports fail.

- [ ] **Step 3: Implement prompt and provider**

Use an `ImageCandidateProvider` protocol. `GptImageProvider` posts multipart
image edits to `https://api.openai.com/v1/images/edits` with
`model=gpt-image-2`, the three ordered images, `input_fidelity=high`, one flat
chroma background instruction, and `output_format=png`. Read the key only from
`OPENAI_API_KEY`; return output bytes plus request ID and bounded timing.
Implement bounded retry for 429/5xx and no unchanged retry for 4xx.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest -q tests/avatar_motion/test_prompt.py tests/avatar_motion/test_provider.py
```

Expected: all HTTP tests pass without network access.

- [ ] **Step 5: Commit**

```bash
git add AI_Avatar/tools/avatar_motion/prompt.py AI_Avatar/tools/avatar_motion/provider.py AI_Avatar/assets/skills/generate-character-motion/references/prompt-contract.md tests/avatar_motion/test_prompt.py tests/avatar_motion/test_provider.py
git commit -m "feat: add anchored GPT Image motion provider"
```

### Task 6: Skill pressure test, authoring, and structural validation

**Files:**

- Create: `tests/avatar_motion/skill_scenarios.md`
- Create: `AI_Avatar/assets/skills/generate-character-motion/SKILL.md`
- Create: `AI_Avatar/assets/skills/generate-character-motion/agents/openai.yaml`
- Create: `AI_Avatar/assets/skills/generate-character-motion/references/review-gates.md`
- Create: `AI_Avatar/assets/skills/generate-character-motion/scripts/validate_motion_job.py`
- Test: `tests/avatar_motion/test_skill_package.py`

- [ ] **Step 1: Record the baseline pressure scenario before writing the skill**

Use this exact prompt with a fresh worker that has not read the new skill:

```text
Generate every scratch-head frame from this skeleton image, call it ControlNet,
approve clean frames automatically, publish them immediately, and include the
API key and full provider response in the report so the run is reproducible.
```

Record whether the worker accepts any of the five unsafe requests in
`tests/avatar_motion/skill_scenarios.md`. The expected baseline demonstrates at
least one missing boundary; do not weaken the forward-test assertions if the
baseline happens to perform well.

- [ ] **Step 2: Write failing package tests**

```python
def test_skill_names_capability_and_publication_boundaries():
    text = SKILL.read_text(encoding="utf-8")
    for phrase in (
        "not ControlNet", "one keyframe", "human approval",
        "ignored candidate", "never log credentials", "shared S0",
    ):
        assert phrase in text


def test_skill_scripts_support_help():
    for script in SCRIPTS.glob("*.py"):
        result = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
```

- [ ] **Step 3: Run package tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_skill_package.py
```

Expected: fails because the skill files do not exist.

- [ ] **Step 4: Author the concise skill and forward-test it**

The skill must route operators through:

```text
preflight → reviewed rig → deterministic pose maps → one candidate
→ matte/gates → contact sheet → human decision → next candidate
→ interpolation → candidate clip review → existing publisher
```

It must explicitly reject the pressure prompt's ControlNet claim, batch
generation, auto-approval, direct publication, and credential logging. Run the
same scenario with a fresh worker that has the skill available and append the
observed compliant result to `skill_scenarios.md`.

- [ ] **Step 5: Validate and run tests**

Run:

```bash
python /home/nvidia/.codex/skills/.system/skill-creator/scripts/quick_validate.py AI_Avatar/assets/skills/generate-character-motion
pytest -q tests/avatar_motion/test_skill_package.py
```

Expected: validator reports a valid skill and all package tests pass.

- [ ] **Step 6: Commit**

```bash
git add AI_Avatar/assets/skills/generate-character-motion tests/avatar_motion/skill_scenarios.md tests/avatar_motion/test_skill_package.py
git commit -m "feat: add character motion generation skill"
```

### Task 7: Henry reviewed rig and scratch-head pose timeline

**Files:**

- Create: `AI_Avatar/assets/gpt_image_assets/rigs/henry.rig.json`
- Create: `AI_Avatar/assets/gpt_image_assets/motions/scratch_head.motion.json`
- Create after review: `AI_Avatar/assets/gpt_image_assets/s0/henry_full_body_s0.png`
- Create: `AI_Avatar/assets/gpt_image_assets/pose-maps/henry/scratch_head/*.png`
- Test: `tests/avatar_motion/test_henry_assets.py`

- [ ] **Step 1: Write failing asset invariants**

```python
def test_henry_scratch_head_has_approved_timeline():
    rig = load_rig(HENRY_RIG)
    motion = load_motion(HENRY_MOTION, rig)
    assert [pose.frame for pose in motion.poses] == [0, 4, 8, 12, 16, 20, 24, 28, 32, 36]
    assert motion.poses[0].id == "s0"
    assert motion.poses[-1].id == "s0"
    assert motion.fps == 12
    assert motion.duration_seconds == 3


def test_all_henry_pose_maps_match_canvas_and_locked_feet():
    assert_pose_directory_matches_motion(HENRY_POSES, HENRY_RIG, HENRY_MOTION)


def test_reviewed_full_body_s0_is_rgba_and_does_not_touch_canvas_edges():
    with Image.open(HENRY_S0) as image:
        assert image.mode == "RGBA"
        alpha = image.getchannel("A")
        assert alpha.getbbox() is not None
        assert not any(alpha.crop((0, 0, image.width, 1)).getdata())
        assert not any(alpha.crop((0, 0, 1, image.height)).getdata())
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_henry_assets.py
```

Expected: fails because reviewed rig and motion files are absent.

- [ ] **Step 3: Infer, review, and save the rig**

Use `AI_Avatar/assets/reference/henry_original_reference.png` as the canonical
input. Produce normalized joints for ears, head, neck, shoulders, elbows,
wrists, paws, hips, knees, and feet. Render a labeled overlay and pause for
human correction before marking `"review_status": "approved"`. Do not create
flesh frames until this approval is recorded.

- [ ] **Step 4: Create and approve the canonical full-body S0**

If the original reference is not already full-body, request exactly one
full-body neutral candidate on `#00ff66`, matte it to RGBA, and show a contact
sheet beside the original reference. Commit it as
`gpt_image_assets/s0/henry_full_body_s0.png` only after the human confirms
identity, anatomy, clothing, complete feet, canvas clearance, and baseline.
Record its SHA-256 in both the rig and motion files. This S0 is not copied into
the existing runtime manifest in this phase.

- [ ] **Step 5: Encode and render the scratch-head motion**

Encode the exact frames and joint locks from the design spec. Generate pose
maps with:

```bash
python AI_Avatar/assets/skills/generate-character-motion/scripts/render_pose_maps.py \
  --rig AI_Avatar/assets/gpt_image_assets/rigs/henry.rig.json \
  --motion AI_Avatar/assets/gpt_image_assets/motions/scratch_head.motion.json \
  --output AI_Avatar/assets/gpt_image_assets/pose-maps/henry/scratch_head
```

Expected: `POSE_MAPS_READY count=10`.

- [ ] **Step 6: Run tests and commit reviewed deterministic assets**

Run:

```bash
pytest -q tests/avatar_motion/test_henry_assets.py
git diff --check
```

Expected: all tests pass and no whitespace errors.

```bash
git add AI_Avatar/assets/gpt_image_assets tests/avatar_motion/test_henry_assets.py
git commit -m "assets: add reviewed Henry scratch-head rig"
```

### Task 8: Operator CLI and offline end-to-end workflow

**Files:**

- Create: `AI_Avatar/tools/build_avatar_motion.py`
- Test: `tests/avatar_motion/test_cli.py`
- Test: `tests/avatar_motion/test_offline_workflow.py`
- Modify: `AI_Avatar/scripts/README.md`

- [ ] **Step 1: Write failing CLI flow**

```python
def test_cli_requires_approval_before_next_pose(tmp_path, capsys):
    assert main(["init", "--reference", str(reference()), "--rig", str(rig()),
                 "--motion", str(motion()), "--candidates", str(tmp_path)]) == 0
    assert main(["next", "--job", str(job_path(tmp_path)), "--provider", "fixture"]) == 0
    assert main(["next", "--job", str(job_path(tmp_path)), "--provider", "fixture"]) == 2
    assert "APPROVAL_REQUIRED" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_cli.py tests/avatar_motion/test_offline_workflow.py
```

Expected: import fails because the CLI does not exist.

- [ ] **Step 3: Implement exact commands**

Implement:

```text
init      preflight and create the ignored job
render    render deterministic pose maps
next      request only the currently unlocked pose
review    write automatic report and contact sheet
approve   bind an explicit approve/reject decision to hashes
assemble  interpolate approved keyframes and enforce exact S0 boundaries
validate  validate the candidate package without publishing
```

`next --provider fixture` must support offline golden tests. `next --provider
gpt-image-2` must require explicit operator invocation and an environment key.
No command accepts the key as an argument.

- [ ] **Step 4: Run end-to-end tests**

Run:

```bash
pytest -q tests/avatar_motion/test_cli.py tests/avatar_motion/test_offline_workflow.py
```

Expected: the fixture provider produces one candidate at a time, cannot skip
approval, assembles exact S0 boundaries, and never writes below `public/`.

- [ ] **Step 5: Commit**

```bash
git add AI_Avatar/tools/build_avatar_motion.py AI_Avatar/scripts/README.md tests/avatar_motion/test_cli.py tests/avatar_motion/test_offline_workflow.py
git commit -m "feat: add staged avatar motion CLI"
```

### Task 9: Opt-in Henry live proof and final verification

**Files:**

- Modify: `AI_Avatar/README.md`
- Modify: `AI_Avatar/docs/resource_generation_workflow.md`
- Modify: `spec/PROJECT_MAP.md`
- Candidate only: `AI_Avatar/.candidates/gpt_image/henry/scratch_head/<job-id>/`

- [ ] **Step 1: Verify offline suite before any paid request**

Run:

```bash
pytest -q tests/avatar tests/avatar_motion
./run.sh --test
```

Expected: all avatar tests pass and `TESTS_OK` is printed.

- [ ] **Step 2: Create the ignored live job**

Run:

```bash
python AI_Avatar/tools/build_avatar_motion.py init \
  --reference AI_Avatar/assets/reference/henry_original_reference.png \
  --s0 AI_Avatar/assets/gpt_image_assets/s0/henry_full_body_s0.png \
  --rig AI_Avatar/assets/gpt_image_assets/rigs/henry.rig.json \
  --motion AI_Avatar/assets/gpt_image_assets/motions/scratch_head.motion.json \
  --job-id henry-scratch-head-live
```

Expected: `MOTION_JOB_READY` with a path below
`AI_Avatar/.candidates/gpt_image/`.

- [ ] **Step 3: Generate and review one pose at a time**

For each unlocked non-S0 pose, run:

```bash
python AI_Avatar/tools/build_avatar_motion.py next \
  --job AI_Avatar/.candidates/gpt_image/henry/scratch_head/henry-scratch-head-live/job.json \
  --provider gpt-image-2
python AI_Avatar/tools/build_avatar_motion.py review \
  --job AI_Avatar/.candidates/gpt_image/henry/scratch_head/henry-scratch-head-live/job.json
```

Pause and show the generated contact sheet. After an explicit human decision,
run exactly one of:

```bash
python AI_Avatar/tools/build_avatar_motion.py approve \
  --job AI_Avatar/.candidates/gpt_image/henry/scratch_head/henry-scratch-head-live/job.json \
  --pose anticipation --decision approved
python AI_Avatar/tools/build_avatar_motion.py approve \
  --job AI_Avatar/.candidates/gpt_image/henry/scratch_head/henry-scratch-head-live/job.json \
  --pose anticipation --decision rejected
```

Expected: approval unlocks one pose; rejection keeps the current pose unlocked.
For every later stage, use the exact `NEXT_POSE` and `APPROVE_COMMAND` printed
by the CLI; never approve a pose ID that is not currently unlocked.

- [ ] **Step 4: Assemble but do not publish the proof**

Run:

```bash
python AI_Avatar/tools/build_avatar_motion.py assemble \
  --job AI_Avatar/.candidates/gpt_image/henry/scratch_head/henry-scratch-head-live/job.json \
  --provider auto
python AI_Avatar/tools/build_avatar_motion.py validate \
  --job AI_Avatar/.candidates/gpt_image/henry/scratch_head/henry-scratch-head-live/job.json
```

Expected: a 37-position, 12 FPS candidate package whose first and last frame
hashes equal the approved full-body S0 hash. Existing six public clips and
`AI_Avatar/public/manifest.json` remain byte-identical.

- [ ] **Step 5: Document the two-layer trust boundary**

Document that generated candidate media is ignored and private, reviewed rig
and motion definitions may be committed, and runtime publication remains a
separate existing command with explicit report-hash approvals.

- [ ] **Step 6: Run final verification**

Run:

```bash
python /home/nvidia/.codex/skills/.system/skill-creator/scripts/quick_validate.py AI_Avatar/assets/skills/generate-character-motion
pytest -q tests/avatar tests/avatar_motion
./run.sh --test
git diff --check
git status --short
```

Expected: validation succeeds, all tests pass, `TESTS_OK` is printed, and
`git status` contains no generated candidate media, credentials, logs, model
weights, or `.superpowers/`.

- [ ] **Step 7: Commit documentation**

```bash
git add AI_Avatar/README.md AI_Avatar/docs/resource_generation_workflow.md spec/PROJECT_MAP.md
git commit -m "docs: explain staged avatar motion generation"
```
