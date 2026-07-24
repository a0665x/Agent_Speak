# AI Avatar Motion Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible Henry sprite pipeline and a Gateway-hosted `/ai_avatar` demo whose six loop states switch only at their shared `S0` boundary.

**Architecture:** Offline Python tools visually inventory, crop, normalize, interpolate, and validate Henry assets before publishing a small approved runtime set. A dedicated React/Vite entry loads the verified manifest, preloads PNG frames, and uses a latest-selection-wins scheduler plus a fixed-canvas renderer. FastAPI and Docker only serve the built static application; they never run interpolation or activate audio devices.

**Tech Stack:** Python 3.11, Pillow, NumPy, pytest, JSON Schema, FILM, RIFE, React 19, TypeScript, Canvas 2D, Vite 8, Vitest, Testing Library, FastAPI, Docker Compose.

---

## File structure

New asset tooling:

- `AI_Avatar/config/verified_asset_inventory.json` — reviewed sheet geometry and core-state source mapping.
- `AI_Avatar/config/interpolation_providers.json` — pinned provider roots, commands, and routing thresholds.
- `AI_Avatar/schemas/asset_inventory.schema.json` — inventory contract.
- `AI_Avatar/schemas/animation_manifest.schema.json` — strict v4 runtime manifest contract.
- `AI_Avatar/tools/avatar_assets/__init__.py` — public tooling exports.
- `AI_Avatar/tools/avatar_assets/inventory.py` — typed inventory parsing and source-bound checks.
- `AI_Avatar/tools/avatar_assets/images.py` — crop, background removal, bounding box, and anchor normalization.
- `AI_Avatar/tools/avatar_assets/interpolation.py` — FILM/RIFE routing and subprocess adapters.
- `AI_Avatar/tools/avatar_assets/quality.py` — candidate-frame quality metrics and statuses.
- `AI_Avatar/tools/avatar_assets/manifest.py` — shared-`S0` manifest builder and validator.
- `AI_Avatar/tools/build_avatar_assets.py` — deterministic command-line build entry.
- `AI_Avatar/tools/setup_interpolation_models.sh` — explicit offline provider setup; never runs during WebUI startup.
- `AI_Avatar/public/manifest.json` — approved runtime manifest copied by Vite.
- `AI_Avatar/public/assets/clips/` — finite, reviewed PNG sequences required by the demo.

New tests:

- `tests/avatar/test_inventory.py`
- `tests/avatar/test_images.py`
- `tests/avatar/test_interpolation.py`
- `tests/avatar/test_quality.py`
- `tests/avatar/test_manifest.py`

Portable avatar runtime:

- `AI_Avatar/frontend/types/avatar.ts` — strict v4 manifest and runtime state types.
- `AI_Avatar/frontend/events/EventBus.ts` — typed avatar-only events.
- `AI_Avatar/frontend/controllers/AvatarStateMachine.ts` — playing and pending state ownership.
- `AI_Avatar/frontend/controllers/ClipScheduler.ts` — frame timing and loop completion.
- `AI_Avatar/frontend/controllers/StateTransitionController.ts` — latest-selection boundary handoff.
- `AI_Avatar/frontend/controllers/VisemeController.ts` — disabled MVP port for later TTS integration.
- `AI_Avatar/frontend/renderers/PngSequenceRenderer.ts` — fixed-canvas renderer.
- `AI_Avatar/frontend/components/HenryAvatar.tsx` — reusable canvas host.

New Gateway frontend:

- `frontend/realtime/avatar.html`
- `frontend/realtime/vite.avatar.config.ts`
- `frontend/realtime/src/avatarLab/manifest.ts`
- `frontend/realtime/src/avatarLab/App.tsx`
- `frontend/realtime/src/avatarLab/main.tsx`
- `frontend/realtime/src/avatarLab/styles.css`
- colocated `*.test.ts` and `*.test.tsx` files for each behavior.

Existing integration files:

- `pyproject.toml`
- `.gitignore`
- `frontend/realtime/package.json`
- `frontend/realtime/tsconfig.json`
- `Dockerfile`
- `src/agent_speak/app.py`
- `tests/test_webui.py`
- `tests/test_docker_runtime.py`
- `AI_Avatar/README.md`
- `AI_Avatar/docs/gif_sprite_architecture.md`
- `AI_Avatar/docs/resource_generation_workflow.md`
- `AI_Avatar/scripts/README.md`
- `AI_Avatar/tests/README.md`
- `spec/PROJECT_MAP.md`
- `spec/UI.md`
- `spec/TESTING.md`

## Task 1: Establish the verified asset inventory

**Files:**

- Create: `AI_Avatar/config/verified_asset_inventory.json`
- Create: `AI_Avatar/schemas/asset_inventory.schema.json`
- Create: `AI_Avatar/tools/avatar_assets/__init__.py`
- Create: `AI_Avatar/tools/avatar_assets/inventory.py`
- Create: `tests/avatar/test_inventory.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add Pillow to the explicit avatar and test dependency groups**

Add one shared compatible constraint to both groups:

```toml
[project.optional-dependencies]
test = [
  "pytest>=8.3,<10",
  "pyyaml>=6,<7",
  "Pillow>=11,<13",
]
avatar = [
  "Pillow>=11,<13",
]
```

- [ ] **Step 2: Write the failing inventory tests**

Create tests that require reviewed mappings for the six MVP states and reject
out-of-bounds cells:

```python
from pathlib import Path

import pytest

from AI_Avatar.tools.avatar_assets.inventory import load_inventory

ROOT = Path(__file__).resolve().parents[2]


def test_verified_inventory_maps_all_mvp_states() -> None:
    inventory = load_inventory(
        ROOT / "AI_Avatar/config/verified_asset_inventory.json",
        ROOT / "AI_Avatar/assets/sheets",
    )
    assert set(inventory.states) == {
        "idle", "listening", "thinking", "speaking", "happy", "error"
    }
    assert inventory.states["idle"].sheet == "03_reaction_happy_laugh.png"
    assert inventory.states["speaking"].sheet == "04_gesture_keyframes.png"
    assert inventory.transition_source.sheet == "01_loop_core_idle_listening_thinking.png"
    assert inventory.composition == "waist_up"


def test_inventory_rejects_a_cell_outside_its_source_image(tmp_path: Path) -> None:
    invalid = tmp_path / "inventory.json"
    invalid.write_text(
        '{"version":"1","canvas":{"width":512,"height":512},'
        '"transition_source":{"sheet":"sheet.png","boxes":[[0,0,999,999]]},'
        '"states":{}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="outside source bounds"):
        load_inventory(invalid, tmp_path)
```

- [ ] **Step 3: Run the tests and verify the missing module failure**

Run:

```bash
python -m pytest tests/avatar/test_inventory.py -q
```

Expected: FAIL because `AI_Avatar.tools.avatar_assets.inventory` does not exist.

- [ ] **Step 4: Implement typed inventory loading and bounds validation**

Use immutable records and validate every configured box against Pillow-reported
source dimensions:

```python
@dataclass(frozen=True)
class FrameSource:
    sheet: str
    boxes: tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True)
class AssetInventory:
    canvas: tuple[int, int]
    composition: str
    transition_source: FrameSource
    states: Mapping[str, FrameSource]


def load_inventory(path: Path, sheets_dir: Path) -> AssetInventory:
    payload = json.loads(path.read_text(encoding="utf-8"))
    inventory = parse_inventory(payload)
    for source in (inventory.transition_source, *inventory.states.values()):
        image_path = sheets_dir / source.sheet
        with Image.open(image_path) as image:
            width, height = image.size
        for left, top, right, bottom in source.boxes:
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise ValueError(f"box outside source bounds: {source.sheet}")
    return inventory
```

The reviewed JSON must map:

- `S0` to the Idle panel in sheet `01`;
- Idle, Listening, and Thinking to rows 1–3 in sheet `03`;
- Speaking to row 1 in sheet `04`;
- Happy and Error to their named panels in sheet `01`.

Use `composition: "waist_up"` for all six states. Sheet `01` contains waist-up
status panels while sheets `03` and `04` contain full-body loops; crop the
loop cells to the same waist-up composition before normalization. Record pixel
boxes by opening each source and verifying the visible cell boundaries, then
retain the largest connected foreground component so card numbers, row labels,
and borders cannot become part of Henry. Do not derive boxes from misleading
filenames.

- [ ] **Step 5: Add a strict JSON Schema and validate the committed inventory**

Require `version`, `canvas`, `transition_source`, and exactly the six MVP state
keys. Each box is a four-integer array with nonnegative coordinates.

Run:

```bash
python -m pytest tests/avatar/test_inventory.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the inventory contract**

```bash
git add pyproject.toml AI_Avatar/config/verified_asset_inventory.json \
  AI_Avatar/schemas/asset_inventory.schema.json AI_Avatar/tools/avatar_assets \
  tests/avatar/test_inventory.py
git commit -m "feat: add verified Henry asset inventory"
```

## Task 2: Crop and normalize deterministic PNG frames

**Files:**

- Create: `AI_Avatar/tools/avatar_assets/images.py`
- Create: `tests/avatar/test_images.py`

- [ ] **Step 1: Write failing normalization tests**

Build synthetic RGBA fixtures in memory and assert transparent bounds, fixed
canvas, and fixed foot anchor:

```python
def test_normalize_places_character_on_fixed_foot_anchor() -> None:
    source = Image.new("RGBA", (100, 100), "white")
    ImageDraw.Draw(source).rectangle((30, 20, 69, 89), fill=(40, 60, 80, 255))
    normalized = normalize_frame(
        source,
        canvas_size=(512, 512),
        anchor=(0.5, 0.92),
        background_tolerance=12,
    )
    alpha_box = normalized.getchannel("A").getbbox()
    assert normalized.size == (512, 512)
    assert alpha_box is not None
    assert alpha_box[3] == round(512 * 0.92)


def test_normalize_centers_character_without_scaling_between_frames() -> None:
    first = normalize_frame(make_fixture(offset_x=0), (512, 512), (0.5, 0.92), 12)
    second = normalize_frame(make_fixture(offset_x=8), (512, 512), (0.5, 0.92), 12)
    assert first.getchannel("A").getbbox() == second.getchannel("A").getbbox()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python -m pytest tests/avatar/test_images.py -q
```

Expected: FAIL because normalization functions are missing.

- [ ] **Step 3: Implement crop, border-background removal, and normalization**

Implement focused functions:

```python
def crop_source(sheet: Image.Image, box: Box) -> Image.Image:
    return sheet.convert("RGBA").crop(box)


def remove_border_background(image: Image.Image, tolerance: int) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA")).copy()
    border = np.concatenate((rgba[0], rgba[-1], rgba[:, 0], rgba[:, -1]))
    background = np.median(border[:, :3], axis=0)
    distance = np.max(np.abs(rgba[:, :, :3].astype(int) - background.astype(int)), axis=2)
    rgba[:, :, 3] = np.where(distance <= tolerance, 0, rgba[:, :, 3])
    return Image.fromarray(rgba, "RGBA")


def normalize_frame(
    image: Image.Image,
    canvas_size: tuple[int, int],
    anchor: tuple[float, float],
    background_tolerance: int,
) -> Image.Image:
    foreground = remove_border_background(image, background_tolerance)
    bounds = foreground.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("frame contains no foreground")
    character = foreground.crop(bounds)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = round(canvas_size[0] * anchor[0] - character.width / 2)
    y = round(canvas_size[1] * anchor[1] - character.height)
    canvas.alpha_composite(character, (x, y))
    return canvas
```

Keep one scale and waist-up baseline across the complete six-state set: compute
the reviewed `S0` visible-head width and bottom baseline once, then normalize
every frame to those reference values rather than independently.

- [ ] **Step 4: Run tests and inspect a six-state contact sheet**

Run:

```bash
python -m pytest tests/avatar/test_images.py -q
```

Expected: PASS. Full-source contact-sheet review is performed after the CLI is
added in Task 6.

- [ ] **Step 5: Commit normalization**

```bash
git add AI_Avatar/tools/avatar_assets/images.py tests/avatar/test_images.py
git commit -m "feat: normalize Henry sprite frames"
```

## Task 3: Enforce the shared `S0` manifest contract

**Files:**

- Modify: `AI_Avatar/config/animation_manifest.json`
- Modify: `AI_Avatar/schemas/animation_manifest.schema.json`
- Create: `AI_Avatar/tools/avatar_assets/manifest.py`
- Create: `tests/avatar/test_manifest.py`

- [ ] **Step 1: Write failing shared-boundary tests**

```python
def test_every_clip_references_the_same_s0_at_both_boundaries() -> None:
    manifest = load_manifest(MANIFEST)
    assert manifest.transition_frame_id == "henry_s0"
    for clip in manifest.clips.values():
        assert clip.loop is True
        assert clip.frames[0] == "henry_s0"
        assert clip.frames[-1] == "henry_s0"


def test_validator_rejects_a_visually_different_tail(tmp_path: Path) -> None:
    manifest = valid_fixture(tmp_path)
    manifest["clips"]["idle_loop"]["frames"][-1] = "fake_s0"
    with pytest.raises(ManifestError, match="shared transition frame"):
        validate_manifest(manifest, tmp_path)
```

- [ ] **Step 2: Run the tests and verify old manifest failure**

Run:

```bash
python -m pytest tests/avatar/test_manifest.py -q
```

Expected: FAIL because the v3 manifest has rows and output paths instead of
explicit frame IDs and a global transition frame.

- [ ] **Step 3: Replace the manifest with the v4 runtime contract**

Use this shape:

```json
{
  "version": "4.0",
  "character": "Henry",
  "viewport": {"width": 512, "height": 512, "anchor_x": 0.5, "anchor_y": 0.92},
  "transition_frame_id": "henry_s0",
  "frames": {
    "henry_s0": {
      "src": "assets/clips/shared/henry_s0.png",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  },
  "clips": {
    "idle_loop": {
      "state": "idle",
      "fps": 12,
      "loop": true,
      "quality_status": "approved",
      "frames": ["henry_s0", "idle_001", "henry_s0"]
    }
  }
}
```

Define six clips and reject unknown properties in the JSON Schema. Keep source
inventory and generation provenance outside the small browser manifest.

- [ ] **Step 4: Implement manifest validation**

`validate_manifest()` must resolve paths beneath the provided public root,
reject path traversal, compute SHA-256 for `S0`, and require every clip to use
the same first and last ID:

```python
if clip.frames[0] != transition_id or clip.frames[-1] != transition_id:
    raise ManifestError(f"{clip_id}: shared transition frame required")
if clip.quality_status != "approved":
    raise ManifestError(f"{clip_id}: clip is not approved")
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python -m pytest tests/avatar/test_manifest.py -q
```

Expected: PASS.

Commit:

```bash
git add AI_Avatar/config/animation_manifest.json \
  AI_Avatar/schemas/animation_manifest.schema.json \
  AI_Avatar/tools/avatar_assets/manifest.py tests/avatar/test_manifest.py
git commit -m "feat: enforce shared avatar transition frame"
```

## Task 4: Add FILM-first and RIFE-fast-path interpolation

**Files:**

- Create: `AI_Avatar/config/interpolation_providers.json`
- Create: `AI_Avatar/tools/avatar_assets/interpolation.py`
- Create: `AI_Avatar/tools/setup_interpolation_models.sh`
- Create: `tests/avatar/test_interpolation.py`
- Modify: `.gitignore`

- [ ] **Step 1: Protect provider checkouts, weights, and candidates**

Add:

```gitignore
# AI Avatar interpolation providers and review artifacts.
AI_Avatar/.providers/
AI_Avatar/.candidates/
runtime/avatar-review/
```

- [ ] **Step 2: Write failing routing and command tests**

```python
def test_large_motion_routes_to_film() -> None:
    router = InterpolationRouter(large_motion_threshold=0.22)
    assert router.select(normalized_motion=0.41).name == "film"


def test_small_motion_routes_to_rife() -> None:
    router = InterpolationRouter(large_motion_threshold=0.22)
    assert router.select(normalized_motion=0.08).name == "rife"


def test_film_builds_the_official_cli_shape(tmp_path: Path) -> None:
    provider = FilmProvider(repo=tmp_path / "film", model=tmp_path / "saved_model")
    command = provider.command(tmp_path / "pair", times=2)
    assert command[:3] == [sys.executable, "-m", "eval.interpolator_cli"]
    assert "--times_to_interpolate" in command


def test_rife_requests_four_way_interpolation(tmp_path: Path) -> None:
    provider = RifeProvider(repo=tmp_path / "rife")
    assert provider.command(tmp_path / "a.png", tmp_path / "b.png", 2)[-2:] == ["--exp", "2"]
```

- [ ] **Step 3: Run the tests and verify failure**

Run:

```bash
python -m pytest tests/avatar/test_interpolation.py -q
```

Expected: FAIL because providers and router do not exist.

- [ ] **Step 4: Implement provider adapters without importing model stacks**

Use a concrete subprocess boundary:

```python
completed = subprocess.run(
    command,
    cwd=provider.repo,
    check=True,
    timeout=provider.timeout_seconds,
    capture_output=True,
    text=True,
)
```

The Gateway process must never import TensorFlow or PyTorch for this feature.

FILM command:

```python
[
    sys.executable, "-m", "eval.interpolator_cli",
    "--pattern", str(pair_dir),
    "--model_path", str(model_path),
    "--times_to_interpolate", str(times),
]
```

RIFE command:

```python
[
    sys.executable, "inference_img.py",
    "--img", str(start), str(end),
    "--exp", str(exponent),
]
```

Normalize provider-specific output names into ordered candidate files at
timestamps `0.25`, `0.50`, and `0.75`.

- [ ] **Step 5: Add an explicit offline setup script**

The script must:

- clone FILM and RIFE into `AI_Avatar/.providers/`;
- pin reviewed Git commits in `interpolation_providers.json`;
- print the official weight locations and expected local paths;
- verify the FILM SavedModel and RIFE `train_log` files;
- stop with a nonzero exit code when weights are missing;
- never write credentials or weights to Git-tracked paths.

Pin and use these reviewed source revisions:

```bash
git clone https://github.com/google-research/frame-interpolation AI_Avatar/.providers/film
git -C AI_Avatar/.providers/film checkout 69f8708f08e62c2edf46a27616a4bfcf083e2076
git clone https://github.com/hzwer/ECCV2022-RIFE AI_Avatar/.providers/rife
git -C AI_Avatar/.providers/rife checkout 5d8adbdd40e12c2c8f91930eff838aebe561c086
```

Weight downloads remain an explicit user action because both official projects
publish them through external storage and their availability must be verified.

- [ ] **Step 6: Run tests and commit**

```bash
python -m pytest tests/avatar/test_interpolation.py -q
git add .gitignore AI_Avatar/config/interpolation_providers.json \
  AI_Avatar/tools/avatar_assets/interpolation.py \
  AI_Avatar/tools/setup_interpolation_models.sh \
  tests/avatar/test_interpolation.py
git commit -m "feat: route avatar frame interpolation"
```

Before committing, run `chmod +x AI_Avatar/tools/setup_interpolation_models.sh`.
Expected: tests PASS; no provider checkout or weight is staged.

## Task 5: Add interpolation quality gates

**Files:**

- Create: `AI_Avatar/tools/avatar_assets/quality.py`
- Create: `tests/avatar/test_quality.py`

- [ ] **Step 1: Write failing quality-status tests**

```python
def test_clean_sequence_is_approved() -> None:
    report = assess_sequence(make_smooth_sequence(), thresholds())
    assert report.status == "approved"


def test_silhouette_jump_requires_keyframe() -> None:
    frames = [fixture_pose(0), fixture_pose(90)]
    report = assess_sequence(frames, thresholds(max_adjacent_delta=0.18))
    assert report.status == "needs_keyframe"
    assert "adjacent_delta" in report.failed_rules


def test_alpha_growth_cannot_be_auto_approved() -> None:
    report = assess_sequence(make_alpha_explosion(), thresholds())
    assert report.status == "needs_review"
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest tests/avatar/test_quality.py -q
```

Expected: FAIL because the quality module is absent.

- [ ] **Step 3: Implement explainable metrics**

Calculate:

- normalized alpha-bounds displacement;
- alpha-area growth;
- mean absolute pixel delta inside the union silhouette;
- center and foot-anchor drift;
- duplicate-frame hashes.

Return:

```python
@dataclass(frozen=True)
class QualityReport:
    status: Literal["approved", "needs_review", "needs_keyframe"]
    metrics: Mapping[str, float]
    failed_rules: tuple[str, ...]
```

Automated checks may downgrade a result but cannot upgrade a generated
candidate to `approved`; final approval is recorded by the build command after
visual review.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/avatar/test_quality.py -q
git add AI_Avatar/tools/avatar_assets/quality.py tests/avatar/test_quality.py
git commit -m "feat: validate avatar interpolation quality"
```

Expected: PASS.

## Task 6: Build and publish the six reviewed runtime clips

**Files:**

- Create: `AI_Avatar/tools/build_avatar_assets.py`
- Create: `AI_Avatar/public/manifest.json`
- Create: `AI_Avatar/public/assets/clips/shared/henry_s0.png`
- Create: reviewed frames below `AI_Avatar/public/assets/clips/{state}/`
- Modify: `tests/avatar/test_manifest.py`

- [ ] **Step 1: Write a failing end-to-end build test**

Use small fixture sheets and fake interpolation providers:

```python
def test_build_publishes_only_approved_clips(tmp_path: Path) -> None:
    result = build_assets(
        inventory=fixture_inventory(tmp_path),
        candidate_root=tmp_path / "candidates",
        public_root=tmp_path / "public",
        providers=FakeProviders(),
        approvals={"idle_loop", "listening_loop"},
    )
    assert result.published == ("idle_loop", "listening_loop")
    assert not (tmp_path / "public/assets/clips/error").exists()
```

- [ ] **Step 2: Run the test and verify failure**

```bash
python -m pytest tests/avatar/test_manifest.py::test_build_publishes_only_approved_clips -q
```

Expected: FAIL because the build orchestration is absent.

- [ ] **Step 3: Implement explicit CLI phases**

Commands:

```text
inspect   -> contact sheet and inventory diagnostics
extract   -> normalized source frames and shared S0
interpolate -> provider candidates plus quality reports
review    -> contact sheets/GIFs for human review
publish   -> only explicitly approved clips and v4 manifest
validate  -> hashes, paths, S0, dimensions, and quality status
```

`publish` requires one `--approve CLIP_ID:REPORT_SHA256` argument per clip so
stale review reports cannot approve regenerated candidates. The `review`
command prints each exact argument; the publisher accepts only a 64-character
lowercase hexadecimal report hash.

- [ ] **Step 4: Generate candidates for the six MVP states**

Run:

```bash
python AI_Avatar/tools/build_avatar_assets.py inspect
python AI_Avatar/tools/build_avatar_assets.py extract
python AI_Avatar/tools/build_avatar_assets.py interpolate --provider auto
python AI_Avatar/tools/build_avatar_assets.py review
```

Expected: review artifacts under `runtime/avatar-review/`; no files yet under
`AI_Avatar/public/`.

- [ ] **Step 5: Visually review every loop**

For each state verify:

- `S0` is the identical first and final image;
- entry and exit do not deform paws, ears, face, headphones, or clothing;
- the foot anchor and character scale remain fixed;
- no label or sheet background leaks into a frame;
- large-motion failures are marked `needs_keyframe`.

Do not approve a failing clip. Add a reviewed keyframe and rerun interpolation
for that shorter segment.

- [ ] **Step 6: Publish the reviewed finite runtime set**

Run `publish` with the six report hashes printed by `review`, then:

```bash
python AI_Avatar/tools/build_avatar_assets.py validate \
  --public-root AI_Avatar/public
```

Expected:

```text
AVATAR_ASSETS_VALID clips=6 transition=henry_s0
```

- [ ] **Step 7: Run tests and commit product artwork**

```bash
python -m pytest tests/avatar -q
git add AI_Avatar/tools/build_avatar_assets.py AI_Avatar/public \
  tests/avatar/test_manifest.py
git commit -m "assets: publish reviewed Henry core loops"
```

Before committing, run:

```bash
git status --short
```

Confirm that only the finite public runtime set is staged; `.providers`,
`.candidates`, models, contact sheets, and logs are absent.

## Task 7: Implement manifest loading and preload readiness

**Files:**

- Modify: `AI_Avatar/frontend/types/avatar.ts`
- Create: `frontend/realtime/src/avatarLab/manifest.ts`
- Create: `frontend/realtime/src/avatarLab/manifest.test.ts`

- [ ] **Step 1: Write failing browser-manifest tests**

```typescript
it('rejects a clip whose boundaries are not the shared S0', () => {
  const payload = fixtureManifest();
  const frames = payload.clips.idle_loop.frames;
  frames[frames.length - 1] = 'idle_002';
  expect(() => parseManifest(payload)).toThrow(/shared transition frame/);
});

it('preloads every unique frame before reporting ready', async () => {
  const load = vi.fn().mockResolvedValue(undefined);
  await preloadManifest(fixtureManifest(), load);
  expect(load).toHaveBeenCalledTimes(uniqueFrameCount);
});
```

- [ ] **Step 2: Run tests and verify failure**

```bash
cd frontend/realtime
npm test -- --run src/avatarLab/manifest.test.ts
```

Expected: FAIL because the avatar manifest loader does not exist.

- [ ] **Step 3: Implement strict browser types and preload**

Define `AvatarState`, `FrameDefinition`, `ClipDefinition`,
`AvatarManifest`, and `PreloadResult` in the portable AI Avatar package.
`loadManifest()` fetches
`/ai_avatar/manifest.json`, parses it, validates the six states and shared
boundary, then preloads every unique `src` with `Image.decode()`.

- [ ] **Step 4: Run tests and commit**

```bash
npm test -- --run src/avatarLab/manifest.test.ts
git add AI_Avatar/frontend/types/avatar.ts \
  frontend/realtime/src/avatarLab/manifest.ts \
  frontend/realtime/src/avatarLab/manifest.test.ts
git commit -m "feat: load verified avatar clips"
```

Expected: PASS.

## Task 8: Implement latest-selection loop-boundary scheduling

**Files:**

- Create: `AI_Avatar/frontend/events/EventBus.ts`
- Create: `AI_Avatar/frontend/controllers/AvatarStateMachine.ts`
- Modify: `AI_Avatar/frontend/controllers/ClipScheduler.ts`
- Create: `AI_Avatar/frontend/controllers/StateTransitionController.ts`
- Create: `AI_Avatar/frontend/controllers/VisemeController.ts`
- Create: `frontend/realtime/src/avatarLab/scheduler.test.ts`

- [ ] **Step 1: Write the scheduler contract as failing tests**

```typescript
it('waits for S0 before switching', () => {
  const scheduler = makeScheduler('idle');
  scheduler.select('listening');
  expect(scheduler.snapshot()).toMatchObject({
    playingState: 'idle',
    pendingState: 'listening',
  });
  scheduler.advanceToFrame('idle_003');
  expect(scheduler.snapshot().playingState).toBe('idle');
  scheduler.advanceToFrame('henry_s0', { loopComplete: true });
  expect(scheduler.snapshot()).toMatchObject({
    playingState: 'listening',
    pendingState: null,
  });
});

it('retains only the latest selection', () => {
  const scheduler = makeScheduler('idle');
  scheduler.select('listening');
  scheduler.select('thinking');
  scheduler.select('speaking');
  expect(scheduler.snapshot().pendingState).toBe('speaking');
});

it('does not restart the active state', () => {
  const scheduler = makeScheduler('idle');
  scheduler.select('idle');
  expect(scheduler.snapshot().pendingState).toBeNull();
});
```

- [ ] **Step 2: Run tests and verify failure**

```bash
cd frontend/realtime
npm test -- --run src/avatarLab/scheduler.test.ts
```

Expected: FAIL because scheduler is missing.

- [ ] **Step 3: Implement the state machine**

`AvatarStateMachine` owns `playingState` and `pendingState`.
`StateTransitionController.select()` overwrites `pendingState`; its
`onLoopBoundary()` promotes only the latest pending state. `ClipScheduler`
owns `frameIndex`, `paused`, FPS timing, and the read-only manifest; it emits
`loop.completed` only after the final shared `S0` has been displayed.
`EventBus` provides typed `state.selected`, `loop.completed`, and
`renderer.failed` events. `VisemeController` exposes `setViseme()` but throws
`VisemeUnavailableError` while `enabled === false`, making the deferred audio
boundary explicit. Failed target preload removes that target from selectable
states without interrupting the active loop.

- [ ] **Step 4: Run tests and commit**

```bash
npm test -- --run src/avatarLab/scheduler.test.ts
git add AI_Avatar/frontend/events/EventBus.ts \
  AI_Avatar/frontend/controllers/AvatarStateMachine.ts \
  AI_Avatar/frontend/controllers/ClipScheduler.ts \
  AI_Avatar/frontend/controllers/StateTransitionController.ts \
  AI_Avatar/frontend/controllers/VisemeController.ts \
  frontend/realtime/src/avatarLab/scheduler.test.ts
git commit -m "feat: schedule avatar changes at loop boundaries"
```

Expected: PASS.

## Task 9: Implement the fixed Canvas renderer

**Files:**

- Create: `AI_Avatar/frontend/renderers/PngSequenceRenderer.ts`
- Delete: `AI_Avatar/frontend/renderers/GifSpriteRenderer.ts`
- Create: `frontend/realtime/src/avatarLab/renderer.test.ts`

- [ ] **Step 1: Write failing renderer tests**

```typescript
it('keeps the viewport fixed across clips', () => {
  const canvas = document.createElement('canvas');
  const renderer = new PngSequenceRenderer(canvas, { width: 512, height: 512 });
  renderer.draw(frame('idle'));
  renderer.draw(frame('speaking'));
  expect([canvas.width, canvas.height]).toEqual([512, 512]);
});

it('never draws an unpreloaded frame', () => {
  const renderer = makeRenderer();
  expect(() => renderer.draw({ id: 'missing', src: '/missing.png' }))
    .toThrow(/not preloaded/);
});
```

- [ ] **Step 2: Run tests and verify failure**

```bash
npm test -- --run src/avatarLab/renderer.test.ts
```

Expected: FAIL because renderer is missing.

- [ ] **Step 3: Implement renderer lifecycle**

Implement `preload()`, `draw()`, `pause()`, `resume()`, `restart()`, and
`dispose()`. Use `requestAnimationFrame` for timing, clear exactly the fixed
viewport, draw one normalized 512×512 PNG at `(0, 0)`, and cancel the frame
request during disposal. Retain the last successfully drawn frame after a
render error and emit `renderer.failed`. Do not add crossfade at clip
boundaries.

- [ ] **Step 4: Run tests and commit**

```bash
npm test -- --run src/avatarLab/renderer.test.ts
git add AI_Avatar/frontend/renderers/PngSequenceRenderer.ts \
  AI_Avatar/frontend/renderers/GifSpriteRenderer.ts \
  frontend/realtime/src/avatarLab/renderer.test.ts
git commit -m "feat: render fixed-canvas Henry animations"
```

Expected: PASS.

## Task 10: Build the `/ai_avatar` interaction page

**Files:**

- Create: `frontend/realtime/avatar.html`
- Modify: `AI_Avatar/frontend/components/HenryAvatar.tsx`
- Create: `frontend/realtime/src/avatarLab/App.tsx`
- Create: `frontend/realtime/src/avatarLab/App.test.tsx`
- Create: `frontend/realtime/src/avatarLab/main.tsx`
- Create: `frontend/realtime/src/avatarLab/styles.css`

- [ ] **Step 1: Write failing UI behavior tests**

```typescript
it('disables state controls until all clips are ready', async () => {
  render(<App manifestLoader={() => pendingManifest.promise} />);
  expect(screen.getByRole('button', { name: 'Listening' })).toBeDisabled();
  pendingManifest.resolve(fixtureReadyManifest());
  expect(await screen.findByText('Assets Ready')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Listening' })).toBeEnabled();
});

it('shows playing and latest queued state', async () => {
  renderReadyApp();
  await user.click(screen.getByRole('button', { name: 'Listening' }));
  await user.click(screen.getByRole('button', { name: 'Thinking' }));
  expect(screen.getByText('Playing: Idle')).toBeVisible();
  expect(screen.getByText('Queued: Thinking')).toBeVisible();
});

it('does not request any audio device', async () => {
  const getUserMedia = vi.fn();
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  });
  const media = vi.spyOn(navigator.mediaDevices, 'getUserMedia');
  renderReadyApp();
  expect(media).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run tests and verify failure**

```bash
npm test -- --run src/avatarLab/App.test.tsx
```

Expected: FAIL because the page does not exist.

- [ ] **Step 3: Implement the page**

Build:

- a fixed 512×512 Henry canvas stage;
- Persistent States buttons: Idle, Listening, Thinking, Speaking;
- Reactions buttons: Happy, Error;
- Pause and Restart controls;
- Assets Ready, Playing, and Queued indicators;
- a collapsible panel for clip, frame, FPS, anchor, source, preload, and quality.

`HenryAvatar` renders the accessible fixed-size `<canvas>` host and forwards
its ref to `PngSequenceRenderer`; it does not accept arbitrary GIF URLs.

Use semantic buttons with at least 44×44 px targets, visible focus, sufficient
contrast, responsive single-column layout below 760 px, and
`prefers-reduced-motion`. Reduced motion lowers FPS but preserves loop-boundary
semantics.

- [ ] **Step 4: Run tests and commit**

```bash
npm test -- --run src/avatarLab/App.test.tsx
git add frontend/realtime/avatar.html AI_Avatar/frontend/components/HenryAvatar.tsx \
  frontend/realtime/src/avatarLab/App.tsx \
  frontend/realtime/src/avatarLab/App.test.tsx \
  frontend/realtime/src/avatarLab/main.tsx \
  frontend/realtime/src/avatarLab/styles.css
git commit -m "feat: add AI avatar motion lab UI"
```

Expected: PASS.

## Task 11: Build and serve the dedicated Vite entry

**Files:**

- Create: `frontend/realtime/vite.avatar.config.ts`
- Modify: `frontend/realtime/package.json`
- Modify: `frontend/realtime/tsconfig.json`
- Modify: `Dockerfile`
- Modify: `src/agent_speak/app.py`
- Modify: `tests/test_webui.py`
- Modify: `tests/test_docker_runtime.py`
- Create: built static output below `web/ai_avatar/`

- [ ] **Step 1: Write failing Gateway and Docker tests**

Add:

```python
@pytest.mark.anyio
async def test_ai_avatar_route_serves_static_demo_without_audio(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        page = await client.get("/ai_avatar")
        manifest = await client.get("/ai_avatar/manifest.json")
    assert page.status_code == 200
    assert '<div id="root"></div>' in page.text
    assert manifest.status_code == 200
    assert manifest.json()["transition_frame_id"] == "henry_s0"
    assert "getUserMedia" not in page.text


def test_docker_image_copies_ai_avatar_build() -> None:
    source = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY AI_Avatar /workspace/AI_Avatar" in source
    assert "COPY --from=realtime-frontend-build /workspace/web/ai_avatar /app/web/ai_avatar" in source
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest tests/test_webui.py tests/test_docker_runtime.py -q
```

Expected: FAIL because `/ai_avatar` and the Docker copy do not exist.

- [ ] **Step 3: Add the Vite build**

`vite.avatar.config.ts`:

```typescript
export default defineConfig({
  base: '/ai_avatar/',
  plugins: [react()],
  publicDir: '../../AI_Avatar/public',
  build: {
    outDir: '../../web/ai_avatar',
    emptyOutDir: true,
    rollupOptions: { input: 'avatar.html' },
  },
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts' },
});
```

Add `vite.avatar.config.ts` to `tsconfig.json`. Extend package scripts:

```json
"build": "tsc -b && vite build && vite build --config vite.tts-clone.config.ts && vite build --config vite.avatar.config.ts",
"build:avatar": "tsc -b && vite build --config vite.avatar.config.ts"
```

Copy `AI_Avatar` into the frontend build stage before building.

- [ ] **Step 4: Mount and serve the built application**

In `create_app()`:

```python
ai_avatar_web_dir = web_dir / "ai_avatar"
ai_avatar_assets = ai_avatar_web_dir / "assets"
if ai_avatar_assets.is_dir():
    app.mount(
        "/ai_avatar/assets",
        StaticFiles(directory=ai_avatar_assets),
        name="ai-avatar-assets",
    )
```

Add `/ai_avatar`, `/ai_avatar/`, and `/ai_avatar/manifest.json` routes with the
same 503 behavior used by the other dedicated WebUIs. The page route reads
`avatar.html`, falling back to `index.html` only if the Vite output naming
changes.

- [ ] **Step 5: Run targeted and frontend tests**

```bash
cd frontend/realtime
npm run build:avatar
cd ../..
python -m pytest tests/test_webui.py tests/test_docker_runtime.py -q
cd frontend/realtime
npm test
```

Expected: all tests PASS and `web/ai_avatar/avatar.html` plus manifest/assets
exist.

- [ ] **Step 6: Commit integration**

```bash
git add frontend/realtime/package.json frontend/realtime/tsconfig.json \
  frontend/realtime/vite.avatar.config.ts Dockerfile \
  src/agent_speak/app.py tests/test_webui.py tests/test_docker_runtime.py \
  web/ai_avatar
git commit -m "feat: serve AI avatar lab from gateway"
```

## Task 12: Reconcile documentation and verify the complete feature

**Files:**

- Modify: `AI_Avatar/README.md`
- Modify: `AI_Avatar/docs/gif_sprite_architecture.md`
- Modify: `AI_Avatar/docs/resource_generation_workflow.md`
- Modify: `AI_Avatar/scripts/README.md`
- Modify: `AI_Avatar/tests/README.md`
- Modify: `spec/PROJECT_MAP.md`
- Modify: `spec/UI.md`
- Modify: `spec/TESTING.md`

- [ ] **Step 1: Write documentation assertions first**

Extend `tests/test_docs.py` to require:

```python
assert "/ai_avatar" in project_map
assert "shared `S0`" in avatar_readme
assert "latest selection" in avatar_readme
assert "FILM" in generation_workflow and "RIFE" in generation_workflow
assert "must not activate" in avatar_readme
```

- [ ] **Step 2: Run the documentation test and verify failure**

```bash
python -m pytest tests/test_docs.py -q
```

Expected: FAIL until the AI Avatar documents describe the implemented paths
and behavior.

- [ ] **Step 3: Rewrite the AI Avatar documentation around verified reality**

Remove the destructive replacement instructions from `AI_Avatar/README.md`.
Document:

- actual sheet inventory and filename/content mismatches;
- source, candidate, approved-public, and runtime directory boundaries;
- the exact shared `S0` rule;
- latest-selection-wins loop scheduling;
- FILM/RIFE setup and quality fallback;
- `/ai_avatar` startup and verification;
- the fact that this MVP never starts audio devices;
- future `listen_once -> external Agent -> speak` integration boundaries.

- [ ] **Step 4: Run complete verification**

From the repository root:

```bash
./run.sh --test
git diff --check
```

Expected:

- Python/avatar tests PASS;
- recorder tests PASS;
- all frontend tests PASS;
- `TESTS_OK`;
- no whitespace errors.

Build and start without activating microphone or speaker playback:

```bash
./run.sh --build
curl -fsS http://127.0.0.1:8765/ai_avatar
curl -fsS http://127.0.0.1:8765/ai_avatar/manifest.json
```

Expected: HTML root and a six-clip manifest with
`"transition_frame_id":"henry_s0"`.

- [ ] **Step 5: Perform browser interaction review**

Open `/ai_avatar`, then:

1. wait for Assets Ready;
2. select Listening, Thinking, and Speaking before Idle finishes;
3. confirm Queued shows only Speaking;
4. confirm Idle completes at `S0`;
5. confirm Speaking begins from the identical `S0`;
6. repeat through Happy and Error;
7. verify fixed viewport/anchor, keyboard focus, narrow layout, and reduced
   motion;
8. verify no microphone permission prompt and no audio playback.

Capture `AI_Avatar/docs/media/ai-avatar-desktop.png` and
`AI_Avatar/docs/media/ai-avatar-transition.gif` for documentation. Do not
capture or commit recordings, voice data, logs, model weights, or private Agent
state.

- [ ] **Step 6: Commit documentation and verification evidence**

```bash
git add AI_Avatar/README.md AI_Avatar/docs AI_Avatar/scripts/README.md \
  AI_Avatar/tests/README.md spec/PROJECT_MAP.md spec/UI.md spec/TESTING.md \
  tests/test_docs.py AI_Avatar/docs/media/ai-avatar-desktop.png \
  AI_Avatar/docs/media/ai-avatar-transition.gif
git commit -m "docs: document AI avatar build and runtime"
```

## Final completion checks

- [ ] `git status -sb` shows only intentional feature changes.
- [ ] `git diff main...HEAD --check` reports no errors.
- [ ] `./run.sh --test` ends with `TESTS_OK`.
- [ ] `AI_Avatar/public/manifest.json` exposes exactly six approved loops.
- [ ] Every loop starts and ends with the same `henry_s0` frame ID and hash.
- [ ] Rapid selections retain only the latest pending state.
- [ ] `/ai_avatar` works from the built Gateway image.
- [ ] No microphone, ASR, TTS, speaker, VLM, or external Agent is started.
- [ ] No credentials, weights, candidates, logs, recordings, or private state
  appear in the diff.
