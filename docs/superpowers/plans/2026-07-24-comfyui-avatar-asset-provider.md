# ComfyUI Avatar Asset Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the sole generative `comfyui_assets` path that submits reviewed FLF2V workflows, preserves original animated previews, and normalizes approved results into exact-S0 PNG sequences accepted by the existing avatar scheduler.

**Architecture:** A sanitized workflow template and motion preset become an ignored ComfyUI job. The provider adapter talks to an external ComfyUI service but has no runtime or publication authority. A deterministic FFmpeg normalizer extracts fixed-FPS frames, replaces both boundaries with the exact approved S0, checks the neighboring frames for visible jumps, and emits the existing runtime candidate clip contract. FILM/RIFE remain optional bounded post-processing providers.

**Tech Stack:** Python 3.11, `httpx`, JSON Schema, Pillow, NumPy, FFmpeg/FFprobe subprocesses, pytest; external ComfyUI with a reviewed FLF2V workflow.

---

## Scope boundary

This plan commits schemas, sanitized workflow/preset metadata, provider code,
offline fixtures, and normalization tests. It does not download Wan/FLF2V
weights, start ComfyUI, or add a live ComfyUI dependency to `/ai_avatar`.
There is no GPT Image fallback or per-keyframe paid-generation task.

### Task 1: ComfyUI motion preset and workflow sanitizer

**Files:**

- Create: `AI_Avatar/assets/comfyui_assets/schemas/comfyui-motion.schema.json`
- Create: `AI_Avatar/assets/comfyui_assets/motion-presets/breathing.json`
- Create: `AI_Avatar/assets/comfyui_assets/workflows/.gitkeep`
- Create: `AI_Avatar/tools/avatar_motion/comfyui_contract.py`
- Test: `tests/avatar_motion/test_comfyui_contract.py`

- [ ] **Step 1: Write failing sanitizer tests**

```python
def test_sanitizer_rejects_absolute_paths_and_credentials(tmp_path):
    workflow = {"1": {"inputs": {"ckpt_name": "/home/user/model.safetensors",
                                  "token": "secret"}}}
    with pytest.raises(ValueError, match="absolute path|credential"):
        sanitize_workflow(workflow)


def test_motion_preset_requires_same_s0_for_first_and_last():
    with pytest.raises(ValueError, match="S0"):
        load_comfyui_motion({**valid_preset(), "last_frame_id": "different"})
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_comfyui_contract.py
```

Expected: import fails because the contract module does not exist.

- [ ] **Step 3: Implement strict preset loading and recursive sanitization**

Reject keys matching `token`, `secret`, `password`, `credential`, and `api_key`;
reject absolute POSIX/Windows paths; require one declared output node; allow
only GIF, WebP, WebM, or MP4 result types; require safe IDs, fixed canvas, FPS,
duration, seed, first frame ID, and last frame ID.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pytest -q tests/avatar_motion/test_comfyui_contract.py
```

Expected: all tests pass.

```bash
git add AI_Avatar/assets/comfyui_assets AI_Avatar/tools/avatar_motion/comfyui_contract.py tests/avatar_motion/test_comfyui_contract.py
git commit -m "feat: define sanitized ComfyUI motion contracts"
```

### Task 2: External ComfyUI provider adapter

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/comfyui_provider.py`
- Test: `tests/avatar_motion/test_comfyui_provider.py`

- [ ] **Step 1: Write failing HTTP contract tests**

```python
def test_provider_submits_polls_and_downloads_only_expected_output(httpx_mock, tmp_path):
    httpx_mock.add_response(url="http://comfy/prompt", json={"prompt_id": "p1"})
    httpx_mock.add_response(url="http://comfy/history/p1", json=completed_history())
    httpx_mock.add_response(url="http://comfy/view?filename=result.webp&type=output", content=webp_bytes())
    result = ComfyUiProvider("http://comfy").generate(job(), tmp_path)
    assert result.preview_path.name == "result.webp"
    assert result.workflow_sha256 == job().workflow_sha256


def test_provider_timeout_is_bounded(httpx_mock, tmp_path):
    httpx_mock.add_response(url="http://comfy/prompt", json={"prompt_id": "p1"})
    httpx_mock.add_response(url="http://comfy/history/p1", json={})
    with pytest.raises(ComfyUiTimeout):
        ComfyUiProvider("http://comfy", timeout_seconds=0).generate(job(), tmp_path)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_comfyui_provider.py
```

Expected: import fails.

- [ ] **Step 3: Implement submission, polling, download, and cancellation**

Inject the first and last image references, motion prompt, dimensions, FPS,
duration, and seed only into declared workflow slots. Poll only the submitted
prompt ID. On bounded cancellation call `/interrupt`; write only safe metadata:

```json
{
  "prompt_id": "p1",
  "workflow_sha256": "<sha256>",
  "seed": 42,
  "elapsed_ms": 1000,
  "media_type": "webp"
}
```

Never copy the full queue/history response into a report.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pytest -q tests/avatar_motion/test_comfyui_provider.py
```

Expected: all tests pass.

```bash
git add AI_Avatar/tools/avatar_motion/comfyui_provider.py tests/avatar_motion/test_comfyui_provider.py
git commit -m "feat: add bounded ComfyUI FLF2V provider"
```

### Task 3: Deterministic animated-media normalization

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/media.py`
- Test: `tests/avatar_motion/test_media.py`

- [ ] **Step 1: Write failing normalization tests**

```python
def test_normalizer_writes_fixed_fps_pngs_with_exact_s0_boundaries(tmp_path):
    source = write_synthetic_animated_webp(tmp_path / "source.webp")
    s0 = write_synthetic_s0(tmp_path / "s0.png")
    result = normalize_media(source, s0, tmp_path / "frames",
                             fps=12, duration_seconds=3, canvas=(512, 512))
    assert len(result.frames) == 37
    assert result.frames[0].read_bytes() == s0.read_bytes()
    assert result.frames[-1].read_bytes() == s0.read_bytes()


def test_normalizer_rejects_wrong_dimensions(tmp_path):
    source = write_synthetic_animated_webp(tmp_path / "source.webp")
    s0 = write_synthetic_s0(tmp_path / "s0.png")
    with pytest.raises(MediaValidationError, match="canvas"):
        normalize_media(source, s0, tmp_path / "frames",
                        fps=12, duration_seconds=3, canvas=(256, 256))
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_media.py
```

Expected: import fails.

- [ ] **Step 3: Implement FFprobe validation and FFmpeg extraction**

Use argument arrays, never `shell=True`. Require tools with `shutil.which`.
Probe JSON, reject undeclared streams and unsafe dimensions, then extract:

```text
ffmpeg -nostdin -v error -i <source> -vf fps=12,scale=512:512:flags=lanczos
       -frames:v 37 <temporary>/frame_%04d.png
```

Write into a temporary sibling directory, verify every PNG, copy exact S0 bytes
over frame 0001 and frame 0037, then atomically rename the directory.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pytest -q tests/avatar_motion/test_media.py
```

Expected: all tests pass when FFmpeg is available; missing FFmpeg reports one
clear skipped integration test while pure validation tests still pass.

```bash
git add AI_Avatar/tools/avatar_motion/media.py tests/avatar_motion/test_media.py
git commit -m "feat: normalize avatar animation media"
```

### Task 4: Shared-S0 neighbor gates and candidate package

**Files:**

- Create: `AI_Avatar/tools/avatar_motion/candidate_clip.py`
- Modify: `AI_Avatar/tools/avatar_motion/review.py`
- Test: `tests/avatar_motion/test_candidate_clip.py`

- [ ] **Step 1: Write failing boundary tests**

```python
def test_visible_penultimate_to_s0_jump_is_rejected(tmp_path):
    frames = sequence_with_large_penultimate_jump(tmp_path)
    report = build_candidate_clip(frames, s0_path(tmp_path), metadata())
    assert report.status == "needs_keyframe"
    assert "loop_exit_delta" in report.failed_rules


def test_candidate_records_source_without_allowing_direct_preview_publish(tmp_path):
    package = build_candidate_clip(clean_frames(tmp_path), s0_path(tmp_path),
                                   metadata(preview="preview/source.webm"))
    assert package.source_type == "comfyui_flf2v"
    assert all(path.suffix == ".png" for path in package.runtime_frames)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_candidate_clip.py
```

Expected: import fails.

- [ ] **Step 3: Implement the converged package**

Calculate normal adjacent metrics plus `S0 → second frame` and `penultimate
frame → S0`. Emit `candidate-clip.json` with relative paths, hashes, source
type, workflow hash, FPS, frame count, canvas, and review status. Do not expose
a method that writes below `AI_Avatar/public/`.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pytest -q tests/avatar_motion/test_candidate_clip.py tests/avatar_motion/test_motion_review.py
```

Expected: all tests pass.

```bash
git add AI_Avatar/tools/avatar_motion/candidate_clip.py AI_Avatar/tools/avatar_motion/review.py tests/avatar_motion/test_candidate_clip.py
git commit -m "feat: converge avatar candidate clip gates"
```

### Task 5: ComfyUI CLI integration and offline workflow

**Files:**

- Modify: `AI_Avatar/tools/build_avatar_motion.py`
- Create: `tests/avatar_motion/test_comfyui_cli.py`
- Modify: `AI_Avatar/scripts/README.md`
- Modify: `AI_Avatar/docs/resource_generation_workflow.md`

- [ ] **Step 1: Write failing CLI test**

```python
def test_comfyui_import_keeps_preview_and_builds_png_candidate(tmp_path, capsys):
    source = write_synthetic_animated_webp(tmp_path / "source.webp")
    s0 = write_synthetic_s0(tmp_path / "s0.png")
    code = main([
        "comfyui-import", "--source", str(source), "--s0", str(s0),
        "--preset", str(BREATHING_PRESET), "--candidates", str(tmp_path),
    ])
    assert code == 0
    assert (tmp_path / "preview/source.webp").is_file()
    assert len(list((tmp_path / "frames").glob("*.png"))) == 37
    assert "COMFYUI_CANDIDATE_READY" in capsys.readouterr().out
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest -q tests/avatar_motion/test_comfyui_cli.py
```

Expected: parser rejects `comfyui-import`.

- [ ] **Step 3: Add two explicit commands**

```text
comfyui-generate  submit a reviewed workflow to an explicit --server URL
comfyui-import    normalize an existing generated preview without network
```

Neither command may publish. `comfyui-generate` must be opt-in and must show
the target server URL before submission.

- [ ] **Step 4: Run offline integration tests**

Run:

```bash
pytest -q tests/avatar_motion/test_comfyui_contract.py \
  tests/avatar_motion/test_comfyui_provider.py \
  tests/avatar_motion/test_media.py \
  tests/avatar_motion/test_candidate_clip.py \
  tests/avatar_motion/test_comfyui_cli.py
```

Expected: all tests pass without a live ComfyUI server.

- [ ] **Step 5: Commit**

```bash
git add AI_Avatar/tools/build_avatar_motion.py AI_Avatar/scripts/README.md AI_Avatar/docs/resource_generation_workflow.md tests/avatar_motion/test_comfyui_cli.py
git commit -m "feat: integrate ComfyUI avatar candidates"
```

### Task 6: Final regression and security verification

**Files:**

- Modify: `AI_Avatar/README.md`
- Modify: `spec/PROJECT_MAP.md`

- [ ] **Step 1: Document deployment and privacy boundaries**

Document that the server URL is deployment-specific; model weights and
generated media stay ignored; workflow JSON must be sanitized; original media
is review-only; PNG sequences are the production scheduler input; and exact S0
plus neighbor gates are mandatory.

- [ ] **Step 2: Run full verification**

Run:

```bash
pytest -q tests/avatar tests/avatar_motion
./run.sh --test
git diff --check
git status --short
```

Expected: all tests pass, `TESTS_OK` is printed, and no model weights,
generated preview media, decoded frames, credentials, ComfyUI history, logs,
or `.superpowers/` are staged.

- [ ] **Step 3: Commit documentation**

```bash
git add AI_Avatar/README.md spec/PROJECT_MAP.md
git commit -m "docs: explain ComfyUI avatar asset workflow"
```
