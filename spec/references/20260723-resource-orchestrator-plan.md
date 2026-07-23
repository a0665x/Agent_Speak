# Extensible GPU Resource Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe one-click ASR/TTS resource reconciliation while keeping the Gateway stable and allowing high-VRAM hosts to run ASR and TTS concurrently.

**Architecture:** A host-owned Python Resource Orchestrator manages fixed Compose worker actions and exposes a permission-restricted Unix socket under `runtime/`. The Gateway proxies typed resource APIs without Docker access; both React pages request profiles and poll operation state. `exclusive` remains the current 11 GB fallback, while `auto` can resolve to `concurrent` when configured model budgets fit.

**Tech Stack:** Python 3.11 standard-library Unix sockets and subprocess argument arrays, FastAPI/Pydantic, Docker Compose v2, React 19/TypeScript, Vitest/Testing Library, pytest/httpx.

---

## Scope and file structure

This plan delivers `auto`, `exclusive`, and single-GPU `concurrent` runtime
policies. It validates `multi_gpu` configuration and preserves per-workload
device fields, but real multi-GPU placement acceptance remains hardware-gated.
`full_pipeline` is present in schemas and returns
`agent_provider_unavailable` until a non-development Agent provider exists.

New Python units:

- `src/agent_speak/resource_types.py`: enums, immutable operation/workload
  records, JSON serialization, and pure profile planning.
- `src/agent_speak/resource_state.py`: atomic ignored-runtime state store.
- `src/agent_speak/resource_supervisor.py`: Unix-socket server, serialized
  reconciler, Compose adapter, and host CLI.
- `src/agent_speak/resource_control.py`: bounded Gateway Unix-socket client.
- `src/agent_speak/resource_routes.py`: public `/api/v1/resources` contract.
- `tests/test_resource_types.py`, `tests/test_resource_state.py`,
  `tests/test_resource_supervisor.py`, `tests/test_resource_api.py`: focused
  hardware-free contracts.

New frontend units:

- `frontend/realtime/src/resources.ts`: typed resource API and polling.
- `frontend/realtime/src/components/ResourceReset.tsx`: shared accessible reset
  control and phase presentation.
- `frontend/realtime/src/components/ResourceReset.test.tsx`: shared behavior.

Existing files stay focused:

- `run.sh` starts/stops the host supervisor and delegates `--asr-up` /
  `--tts-up` to reconciliation.
- `compose.yaml` passes socket/policy configuration to the stable Gateway.
- `src/agent_speak/app.py`, `schemas.py`, `model_control.py`, and
  `tts_clone_routes.py` consume dynamic resource truth.
- `frontend/realtime/src/App.tsx` and `ttsClone/App.tsx` integrate the shared
  control without merging their audio state machines.
- Each page keeps its existing stylesheet and localization catalog.

### Task 1: Define resource types, profiles, and conservative policy planning

**Files:**
- Create: `src/agent_speak/resource_types.py`
- Create: `tests/test_resource_types.py`
- Modify: `src/agent_speak/config.py`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Write failing profile and policy tests**

```python
from agent_speak.resource_types import (
    MemoryBudget,
    ResourcePolicy,
    ResourceProfile,
    Workload,
    plan_profile,
    resolve_policy,
)


def test_auto_uses_exclusive_when_combined_budget_does_not_fit() -> None:
    budget = MemoryBudget(
        usable_mb=11_000,
        reserve_mb=1_500,
        asr_mb=6_500,
        correction_mb=1_000,
        tts_mb=9_500,
    )
    assert resolve_policy(ResourcePolicy.AUTO, budget) is ResourcePolicy.EXCLUSIVE


def test_auto_uses_concurrent_when_all_inference_budgets_fit() -> None:
    budget = MemoryBudget(
        usable_mb=48_000,
        reserve_mb=2_000,
        asr_mb=6_500,
        correction_mb=1_000,
        tts_mb=9_500,
    )
    assert resolve_policy(ResourcePolicy.AUTO, budget) is ResourcePolicy.CONCURRENT


def test_profiles_are_declarative_and_full_pipeline_requires_real_agent() -> None:
    assert plan_profile(ResourceProfile.ASR_ONLY) == {
        Workload.ASR,
        Workload.CORRECTION,
    }
    assert plan_profile(ResourceProfile.TTS_ONLY) == {Workload.TTS}
    assert plan_profile(ResourceProfile.FULL_PIPELINE) == {
        Workload.ASR,
        Workload.CORRECTION,
        Workload.AGENT,
        Workload.TTS,
    }
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m pytest tests/test_resource_types.py -q
```

Expected: collection fails because `agent_speak.resource_types` does not exist.

- [ ] **Step 3: Implement the pure resource domain**

Create enums for `ResourcePolicy(auto, exclusive, concurrent, multi_gpu)`,
`ResourceProfile(asr_only, tts_only, full_pipeline)`,
`Workload(asr, correction, agent, tts)`, and
`OperationPhase(queued, draining, releasing, starting, warming, ready, failed,
rolled_back, cancelled)`. Implement:

```python
@dataclass(frozen=True, slots=True)
class MemoryBudget:
    usable_mb: int
    reserve_mb: int
    asr_mb: int
    correction_mb: int
    tts_mb: int

    @property
    def concurrent_required_mb(self) -> int:
        return self.reserve_mb + self.asr_mb + self.correction_mb + self.tts_mb


def resolve_policy(requested: ResourcePolicy, budget: MemoryBudget) -> ResourcePolicy:
    if requested is not ResourcePolicy.AUTO:
        return requested
    return (
        ResourcePolicy.CONCURRENT
        if budget.usable_mb >= budget.concurrent_required_mb
        else ResourcePolicy.EXCLUSIVE
    )


PROFILE_WORKLOADS = {
    ResourceProfile.ASR_ONLY: frozenset({Workload.ASR, Workload.CORRECTION}),
    ResourceProfile.TTS_ONLY: frozenset({Workload.TTS}),
    ResourceProfile.FULL_PIPELINE: frozenset(
        {Workload.ASR, Workload.CORRECTION, Workload.AGENT, Workload.TTS}
    ),
}


def plan_profile(profile: ResourceProfile) -> set[Workload]:
    return set(PROFILE_WORKLOADS[profile])
```

Add validated settings with conservative defaults:

```python
resource_policy: Literal["auto", "exclusive", "concurrent", "multi_gpu"] = "auto"
resource_socket_path: Path = Path("/app/runtime/resource-control/control.sock")
resource_reserve_mb: int = 1500
resource_asr_budget_mb: int = 6500
resource_correction_budget_mb: int = 1000
resource_tts_budget_mb: int = 9500
resource_drain_timeout_seconds: float = 10.0
resource_start_timeout_seconds: float = 300.0
resource_operation_timeout_seconds: float = 420.0
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_resource_types.py tests/test_contracts.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the domain boundary**

```bash
git add src/agent_speak/resource_types.py src/agent_speak/config.py \
  tests/test_resource_types.py tests/test_contracts.py
git commit -m "feat: define GPU resource policies and profiles"
```

### Task 2: Add atomic, privacy-safe operation state

**Files:**
- Create: `src/agent_speak/resource_state.py`
- Create: `tests/test_resource_state.py`
- Modify: `.gitignore`
- Modify: `.dockerignore`

- [ ] **Step 1: Write failing atomic-state and redaction tests**

```python
def test_state_store_round_trips_one_bounded_snapshot(tmp_path: Path) -> None:
    store = ResourceStateStore(tmp_path / "resource-control" / "state.json")
    snapshot = ResourceSnapshot.initial(
        requested_policy=ResourcePolicy.AUTO,
        resolved_policy=ResourcePolicy.EXCLUSIVE,
        profile=ResourceProfile.ASR_ONLY,
    )
    store.write(snapshot)
    assert store.read() == snapshot
    assert not list(tmp_path.rglob("*.tmp"))


def test_state_store_rejects_unknown_or_oversized_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"private_text":"' + ("x" * 70_000) + '"}', encoding="utf-8")
    with pytest.raises(ResourceStateError):
        ResourceStateStore(path, max_bytes=64 * 1024).read()
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m pytest tests/test_resource_state.py -q
```

Expected: collection fails because `ResourceStateStore` does not exist.

- [ ] **Step 3: Implement immutable snapshots and atomic replacement**

Add `WorkloadStatus`, `ResourceOperation`, and `ResourceSnapshot` dataclasses to
`resource_types.py`. Their `to_dict()` output must contain only enum values,
operation IDs, timestamps, model IDs, generic device classes, lifecycle,
stable error codes, and bounded hints.

Implement `ResourceStateStore.write()` with same-directory `NamedTemporaryFile`,
`flush()`, `os.fsync()`, `os.chmod(temp, 0o600)`, and `os.replace()`.
`read()` must reject files over 64 KiB, unknown keys, invalid enums, and invalid
operation IDs. Never persist raw commands or exception strings.

- [ ] **Step 4: Verify state tests and repository privacy**

Run:

```bash
python -m pytest tests/test_resource_types.py tests/test_resource_state.py -q
git check-ignore runtime/resource-control/state.json
```

Expected: tests pass and the runtime state path is ignored.

- [ ] **Step 5: Commit state persistence**

```bash
git add src/agent_speak/resource_types.py src/agent_speak/resource_state.py \
  tests/test_resource_state.py .gitignore .dockerignore
git commit -m "feat: persist bounded resource operation state"
```

### Task 3: Implement the serialized host Resource Orchestrator

**Files:**
- Create: `src/agent_speak/resource_supervisor.py`
- Create: `tests/test_resource_supervisor.py`

- [ ] **Step 1: Write failing reconciliation tests with a fake lifecycle adapter**

```python
class FakeLifecycle:
    def __init__(self, ready: set[Workload]) -> None:
        self.ready = set(ready)
        self.calls: list[tuple[str, Workload]] = []

    def stop(self, workload: Workload) -> None:
        self.calls.append(("stop", workload))
        self.ready.discard(workload)

    def start(self, workload: Workload) -> None:
        self.calls.append(("start", workload))
        self.ready.add(workload)

    def is_ready(self, workload: Workload) -> bool:
        return workload in self.ready


def test_exclusive_reset_releases_peer_before_starting_target(tmp_path: Path) -> None:
    lifecycle = FakeLifecycle({Workload.ASR, Workload.CORRECTION})
    supervisor = ResourceSupervisor.for_test(
        lifecycle=lifecycle,
        state_path=tmp_path / "state.json",
        policy=ResourcePolicy.EXCLUSIVE,
    )
    operation = supervisor.reset(Workload.TTS)
    supervisor.wait(operation.id)
    assert lifecycle.calls == [
        ("stop", Workload.CORRECTION),
        ("stop", Workload.ASR),
        ("start", Workload.TTS),
    ]
    assert supervisor.snapshot().operation.phase is OperationPhase.READY


def test_concurrent_reset_keeps_ready_peer_resident(tmp_path: Path) -> None:
    lifecycle = FakeLifecycle({Workload.ASR, Workload.CORRECTION})
    supervisor = ResourceSupervisor.for_test(
        lifecycle=lifecycle,
        state_path=tmp_path / "state.json",
        policy=ResourcePolicy.CONCURRENT,
    )
    operation = supervisor.reset(Workload.TTS)
    supervisor.wait(operation.id)
    assert lifecycle.calls == [("start", Workload.TTS)]


def test_incompatible_requests_share_one_serial_operation(tmp_path: Path) -> None:
    lifecycle = BlockingLifecycle()
    supervisor = ResourceSupervisor.for_test(
        lifecycle=lifecycle,
        state_path=tmp_path / "state.json",
        policy=ResourcePolicy.EXCLUSIVE,
    )
    first = supervisor.reconcile(ResourceProfile.TTS_ONLY)
    second = supervisor.reconcile(ResourceProfile.ASR_ONLY)
    assert second.id == first.id
    assert second.phase is not OperationPhase.READY
```

Add tests for: idempotent same-profile request, `full_pipeline` rejection with
`agent_provider_unavailable`, one rollback attempt, restart of a desired
workload, policy-aware ensure of a non-desired workload, startup timeout, and no
exception message in persisted/logged state.

- [ ] **Step 2: Run the supervisor tests and verify RED**

Run:

```bash
python -m pytest tests/test_resource_supervisor.py -q
```

Expected: collection fails because `ResourceSupervisor` does not exist.

- [ ] **Step 3: Implement the reconciler with one background operation**

Define a `LifecycleAdapter` protocol:

```python
class LifecycleAdapter(Protocol):
    def start(self, workload: Workload) -> None:
        raise NotImplementedError

    def stop(self, workload: Workload) -> None:
        raise NotImplementedError

    def is_ready(self, workload: Workload) -> bool:
        raise NotImplementedError

    def usable_gpu_memory_mb(self) -> int:
        raise NotImplementedError
```

`ResourceSupervisor.reconcile()` must validate the profile, acquire one lock,
write `queued`, and start one daemon thread. The thread computes stop/start
sets from requested profile and resolved policy, writes every phase atomically,
waits with monotonic deadlines, and commits `ready`. On failure it records a
stable error code and performs one rollback to `last_ready_profile`.

`exclusive` stop order is correction then ASR before TTS; reverse reconciliation
stops TTS before ASR then correction starts. Exact profile reconciliation makes
its profile the desired set under every policy. `reset(workload)` is
policy-aware: under `exclusive` it releases the incompatible group before
starting the target; under `concurrent` it adds a missing target to the desired
set without stopping healthy peers. An already desired target is stopped and
started.

- [ ] **Step 4: Implement the fixed Compose adapter and Unix protocol**

`ComposeLifecycleAdapter` receives a preconstructed argument prefix such as:

```python
[
    "docker", "compose",
    "-f", "/workspace/compose.yaml",
    "-f", "/workspace/compose.gpu.yaml",
]
```

It maps enums to fixed argument arrays:

```python
START_COMMANDS = {
    Workload.ASR: ("--profile", "asr", "up", "-d", "--no-deps", "asr-worker"),
    Workload.CORRECTION: (
        "--profile", "asr", "up", "-d", "--no-deps", "correction-worker"
    ),
    Workload.TTS: ("--profile", "tts", "up", "-d", "--no-deps", "tts-worker"),
}
STOP_SERVICES = {
    Workload.ASR: "asr-worker",
    Workload.CORRECTION: "correction-worker",
    Workload.TTS: "tts-worker",
}
```

Use
`subprocess.run(argv, shell=False, check=True, timeout=self.command_timeout)`.
Read health
from fixed Compose service IDs plus `docker inspect`; never accept service names
or command fragments from socket input.

GPU inventory uses this fixed command with `shell=False`:

```python
[
    "nvidia-smi",
    "--query-gpu=index,memory.total,memory.free",
    "--format=csv,noheader,nounits",
]
```

Parse exactly three integer columns per line, reject negative or malformed
values, and apply configured `AGENT_SPEAK_*_GPU_DEVICES` indices. For
single-GPU `auto`, policy resolution uses that device's total memory minus the
configured reserve; immediately before starting a missing workload, require
its configured budget to fit current free memory. `multi_gpu` requires every
configured workload index to exist and never derives assignments from request
data.

The Unix server accepts one JSON line up to 16 KiB:

```json
{"action":"snapshot"}
{"action":"reconcile","profile":"asr_only"}
{"action":"reset","workload":"tts"}
{"action":"shutdown"}
```

Create the socket parent with mode `0700`, socket mode `0600`, response limit
64 KiB, and unlink only the exact configured socket at clean startup/shutdown.

- [ ] **Step 5: Run all supervisor tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_resource_types.py tests/test_resource_state.py \
  tests/test_resource_supervisor.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the host control plane**

```bash
git add src/agent_speak/resource_supervisor.py tests/test_resource_supervisor.py
git commit -m "feat: add serialized host resource orchestrator"
```

### Task 4: Integrate supervisor lifecycle into `run.sh` without restarting Gateway

**Files:**
- Modify: `run.sh`
- Modify: `compose.yaml`
- Modify: `compose.gpu.yaml`
- Modify: `tests/test_docker_runtime.py`

- [ ] **Step 1: Replace old mutual-exclusion assertions with failing stable-Gateway tests**

Add tests that use the existing fake Docker binary plus a fake supervisor CLI:

```python
def test_asr_and_tts_operator_modes_delegate_to_resource_reconcile(tmp_path: Path) -> None:
    env, docker_log, supervisor_log = _resource_env(tmp_path)
    for option, profile in (("--asr-up", "asr_only"), ("--tts-up", "tts_only")):
        docker_log.write_text("", encoding="utf-8")
        supervisor_log.write_text("", encoding="utf-8")
        result = subprocess.run(
            [str(ROOT / "run.sh"), option],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert f"reconcile {profile}" in supervisor_log.read_text(encoding="utf-8")
        calls = docker_log.read_text(encoding="utf-8")
        assert "up -d gateway" in calls
        assert "up -d gateway asr-worker" not in calls
        assert "up -d gateway tts-worker" not in calls


def test_gateway_has_no_docker_socket_or_static_gpu_mode() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    gateway = compose["services"]["gateway"]
    assert "/var/run/docker.sock" not in str(gateway)
    assert "AGENT_SPEAK_GPU_MODE" not in gateway["environment"]
    assert gateway["environment"]["AGENT_SPEAK_RESOURCE_SOCKET"] == (
        "/app/runtime/resource-control/control.sock"
    )
```

Also test `--down` requests supervisor shutdown, stale PID/socket recovery is
bounded, `--test` never starts the supervisor, and the environment whitelist
accepts only the documented resource settings.

- [ ] **Step 2: Run lifecycle tests and verify RED**

Run:

```bash
python -m pytest tests/test_docker_runtime.py -q
```

Expected: failures show direct worker start/stop and static
`AGENT_SPEAK_GPU_MODE`.

- [ ] **Step 3: Add run-script supervisor helpers**

Add:

```bash
resource_runtime_dir() {
  printf '%s/resource-control' "${AGENT_SPEAK_RUNTIME_PATH:-./runtime}"
}

resource_cli() {
  PYTHONPATH="$ROOT_DIR/src" python3 -m agent_speak.resource_supervisor \
    --socket "$(resource_runtime_dir)/control.sock" client "$@"
}

start_resource_supervisor() {
  local control_dir pid_file
  control_dir=$(resource_runtime_dir)
  pid_file="$control_dir/supervisor.pid"
  mkdir -p -- "$control_dir"
  chmod 0700 "$control_dir"
  if resource_cli ping >/dev/null 2>&1; then return 0; fi
  PYTHONPATH="$ROOT_DIR/src" nohup python3 -m agent_speak.resource_supervisor \
    --root "$ROOT_DIR" \
    --socket "$control_dir/control.sock" \
    --state "$control_dir/state.json" \
    --policy "${AGENT_SPEAK_RESOURCE_POLICY:-auto}" \
    server >>"$control_dir/supervisor.log" 2>&1 &
  printf '%s\n' "$!" >"$pid_file"
  chmod 0600 "$pid_file"
  for _ in $(seq 1 50); do
    resource_cli ping >/dev/null 2>&1 && return 0
    sleep 0.1
  done
  echo "ERROR: resource supervisor failed to start" >&2
  return 1
}
```

The actual implementation must pass each Compose file as a separate
`--compose-file` argument and inherit the accelerator/path whitelist. It must
not construct a shell command string.

- [ ] **Step 4: Keep Gateway stable and delegate profiles**

Refactor:

```bash
start_control_plane() {
  start_resource_supervisor
  compose up -d gateway
  wait_for_health
}

start_asr_mode() {
  start_control_plane
  resource_cli reconcile asr_only --wait
}

start_tts_mode() {
  if [[ "$ACCELERATOR_SELECTED" != nvidia ]]; then
    echo "ERROR: TTS requires NVIDIA acceleration." >&2
    return 1
  fi
  start_control_plane
  resource_cli reconcile tts_only --wait
}
```

Remove `AGENT_SPEAK_GPU_MODE` from Gateway Compose environment. Add resource
socket, policy, budgets, and timeouts. Add per-service
`NVIDIA_VISIBLE_DEVICES` variables to `compose.gpu.yaml` without changing their
defaults.

`--status` reads `/api/v1/resources` after Gateway health and prints
`resource_policy`, `profile`, and workload states. `--down` asks the supervisor
to shut down before `compose down`.

- [ ] **Step 5: Run shell and lifecycle tests**

Run:

```bash
bash -n run.sh
python -m pytest tests/test_docker_runtime.py -q
```

Expected: all pass and no Docker socket appears in tracked Compose files.

- [ ] **Step 6: Commit stable lifecycle integration**

```bash
git add run.sh compose.yaml compose.gpu.yaml tests/test_docker_runtime.py
git commit -m "feat: reconcile workers without restarting gateway"
```

### Task 5: Expose bounded Gateway resource APIs

**Files:**
- Create: `src/agent_speak/resource_control.py`
- Create: `src/agent_speak/resource_routes.py`
- Create: `tests/test_resource_api.py`
- Modify: `src/agent_speak/schemas.py`
- Modify: `src/agent_speak/app.py`

- [ ] **Step 1: Write failing Unix-client and API tests**

```python
@pytest.mark.anyio
async def test_resource_api_returns_snapshot_and_accepts_profile(tmp_path: Path) -> None:
    control = FakeResourceControl(snapshot=ready_asr_snapshot())
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
        resource_control=control,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        status = await client.get("/api/v1/resources")
        accepted = await client.post(
            "/api/v1/resources/reconcile", json={"profile": "tts_only"}
        )
    assert status.status_code == 200
    assert status.json()["resolved_policy"] == "exclusive"
    assert accepted.status_code == 202
    assert control.calls == [("reconcile", "tts_only")]


@pytest.mark.anyio
async def test_resource_api_rejects_unknown_values_and_maps_missing_supervisor(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", runtime_dir=tmp_path / "runtime"),
        resource_control=UnavailableResourceControl(),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        invalid = await client.post(
            "/api/v1/resources/reconcile", json={"profile": "shell"}
        )
        unavailable = await client.get("/api/v1/resources")
    assert invalid.status_code == 422
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "resource_supervisor_unavailable"
```

Test socket timeout, oversized response, invalid JSON, operation lookup, reset,
idempotent `202`, and absence of raw exception messages.

- [ ] **Step 2: Run API tests and verify RED**

Run:

```bash
python -m pytest tests/test_resource_api.py -q
```

Expected: collection fails because the resource client/routes do not exist.

- [ ] **Step 3: Implement the bounded Unix client**

`ResourceControlClient` connects only to its configured `Path`, sends one
newline-delimited JSON request, applies connect/read timeouts, reads at most
64 KiB, and closes. Methods:

```python
def snapshot(self) -> ResourceSnapshot:
    return ResourceSnapshot.from_dict(self._request({"action": "snapshot"}))

def reconcile(self, profile: ResourceProfile) -> ResourceOperation:
    return ResourceOperation.from_dict(
        self._request({"action": "reconcile", "profile": profile.value})
    )

def reset(self, workload: Workload) -> ResourceOperation:
    return ResourceOperation.from_dict(
        self._request({"action": "reset", "workload": workload.value})
    )

def operation(self, operation_id: str) -> ResourceOperation:
    return ResourceOperation.from_dict(
        self._request({"action": "operation", "operation_id": operation_id})
    )
```

Map socket absence/refusal/timeout and invalid response to:

```python
PlatformError(
    "resource_supervisor_unavailable",
    "Resource supervisor is unavailable",
    status_code=503,
    stage="resources",
    retryable=True,
    details={"operator_hint": "./run.sh --status"},
)
```

- [ ] **Step 4: Add Pydantic schemas and routes**

Add typed response/input schemas for policy, profile, workload lifecycle,
operation, reconcile input, and reset response. Routes:

```python
@router.get("", response_model=ResourceSnapshotResponse)
async def resources() -> ResourceSnapshotResponse:
    snapshot = await run_sync(control.snapshot)
    return snapshot_response(snapshot)

@router.post(
    "/reconcile",
    response_model=ResourceOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reconcile(body: ResourceReconcileInput) -> ResourceOperationResponse:
    operation = await run_sync(
        control.reconcile,
        ResourceProfile(body.profile),
    )
    return operation_response(operation)

@router.post(
    "/{workload}/reset",
    response_model=ResourceOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reset(workload: WorkloadLiteral) -> ResourceOperationResponse:
    operation = await run_sync(control.reset, Workload(workload))
    return operation_response(operation)

@operations_router.get(
    "/{operation_id}",
    response_model=ResourceOperationResponse,
)
async def operation(
    operation_id: Annotated[str, Path(pattern=OPERATION_ID_RE)],
) -> ResourceOperationResponse:
    current = await run_sync(control.operation, operation_id)
    return operation_response(current)
```

Use `/api/v1/resources` for `router` and
`/api/v1/resource-operations` for `operations_router`. Inject
`resource_control` into `create_app()` for tests and register both routers.

- [ ] **Step 5: Run API and existing app tests**

Run:

```bash
python -m pytest tests/test_resource_api.py tests/test_app.py \
  tests/test_contracts.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit the public control contract**

```bash
git add src/agent_speak/resource_control.py src/agent_speak/resource_routes.py \
  src/agent_speak/schemas.py src/agent_speak/app.py \
  tests/test_resource_api.py
git commit -m "feat: expose bounded resource reconciliation API"
```

### Task 6: Derive ASR and TTS readiness dynamically

**Files:**
- Modify: `src/agent_speak/model_control.py`
- Modify: `src/agent_speak/tts_clone_routes.py`
- Modify: `src/agent_speak/app.py`
- Modify: `src/agent_speak/schemas.py`
- Modify: `tests/test_model_control.py`
- Modify: `tests/test_tts_clone_api.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing stopped-worker catalog and concurrent-TTS tests**

```python
def test_catalog_keeps_pinned_options_when_asr_worker_is_stopped() -> None:
    service = ModelCatalogService(
        worker=FailingWorkerControl(),
        correction_ready=lambda: False,
    )
    catalog = service.catalog()
    assert [item.id for item in catalog.asr] == [
        "qwen3-asr-1.7b",
        "breeze-asr-25",
        "faster-whisper-small",
    ]
    assert catalog.active.state == "unavailable"
    assert catalog.active.error_code == "asr_worker_unavailable"


@pytest.mark.anyio
async def test_tts_status_uses_workload_truth_not_static_gpu_mode(
    tmp_path: Path,
) -> None:
    app = clone_app(
        tmp_path,
        resources=FakeResourceControl(snapshot=concurrent_ready_snapshot()),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/tts-clone/status")
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["gpu_mode"] == "tts"
    assert response.json()["resource_policy"] == "concurrent"
```

Also test ASR session creation rejects a non-ready ASR workload with
`asr_resource_not_ready`, and TTS synthesis rejects non-ready TTS with
`tts_resource_not_ready`.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m pytest tests/test_model_control.py tests/test_tts_clone_api.py \
  tests/test_app.py -q
```

Expected: worker failure escapes and TTS still checks `settings.gpu_mode`.

- [ ] **Step 3: Make model catalogs resilient**

In `ModelCatalogService.catalog()`, catch only the stable
`asr_worker_unavailable` error and pass the existing
`UnavailableWorkerModelControl().snapshot()` to `_catalog()`. Keep the three
pinned ASR options visible with `ready=False`. Activation must still fail while
the workload is unavailable.

- [ ] **Step 4: Replace static mode checks with workload readiness**

Pass a `ResourceControl` into the TTS router. `_require_runtime()` checks:

```python
snapshot = resources.snapshot()
tts = snapshot.workloads[Workload.TTS]
if not tts.desired:
    raise PlatformError(
        "tts_resource_not_desired",
        "TTS resources are not requested",
        status_code=409,
        stage="tts_clone",
        details={"operator_hint": "Use Reset TTS resources"},
    )
if not tts.ready or not provider.is_ready():
    raise PlatformError(
        "tts_resource_not_ready",
        "TTS resources are still warming",
        status_code=503,
        stage="tts_clone",
        retryable=True,
        details={"operator_hint": "./run.sh --logs tts-worker"},
    )
```

Keep the existing `TTSCloneStatus.gpu_mode: asr|tts` field for compatibility:
it is `tts` whenever TTS is desired and `asr` otherwise. Add the
`resource_policy: auto|exclusive|concurrent|multi_gpu` field, while `state`,
`ready`, and errors come from the TTS workload plus provider health. Preserve
legacy behavior through a compatibility
`SettingsResourceControl` only when no supervisor client is injected.

Before creating an ASR session or activating a model, verify the ASR workload
is desired and ready. Do not change the existing provider/session contracts.

- [ ] **Step 5: Run focused and contract tests**

Run:

```bash
python -m pytest tests/test_model_control.py tests/test_tts_clone_api.py \
  tests/test_app.py tests/test_sessions_pipeline.py tests/test_contracts.py -q
```

Expected: all pass and pinned selectors remain in unavailable catalogs.

- [ ] **Step 6: Commit dynamic readiness**

```bash
git add src/agent_speak/model_control.py src/agent_speak/tts_clone_routes.py \
  src/agent_speak/app.py src/agent_speak/schemas.py \
  tests/test_model_control.py tests/test_tts_clone_api.py tests/test_app.py
git commit -m "fix: derive inference readiness from resource workloads"
```

### Task 7: Build a shared accessible reset control

**Files:**
- Create: `frontend/realtime/src/resources.ts`
- Create: `frontend/realtime/src/components/ResourceReset.tsx`
- Create: `frontend/realtime/src/components/ResourceReset.test.tsx`
- Modify: `frontend/realtime/src/styles.css`
- Modify: `frontend/realtime/src/ttsClone/styles.css`

- [ ] **Step 1: Write failing API polling tests**

```typescript
test('retries temporary gateway loss until the operation is ready', async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn()
    .mockRejectedValueOnce(new TypeError('network'))
    .mockResolvedValueOnce(jsonResponse({ id: 'op_123', phase: 'warming' }))
    .mockResolvedValueOnce(jsonResponse({ id: 'op_123', phase: 'ready' }));
  const resultPromise = waitForResourceOperation('op_123', {
    fetcher,
    intervalMs: 100,
    timeoutMs: 1_000,
  });
  await vi.advanceTimersByTimeAsync(300);
  await expect(resultPromise).resolves.toMatchObject({ phase: 'ready' });
});
```

Test `POST /api/v1/resources/reconcile`,
`POST /api/v1/resources/{workload}/reset`, stable API errors, timeout, failed
and rolled-back terminal states.

- [ ] **Step 2: Write failing component behavior tests**

```tsx
test('shows progress, prevents duplicate reset, and announces ready', async () => {
  const onReset = vi.fn().mockResolvedValue(undefined);
  render(
    <ResourceReset
      label="Reset ASR resources"
      phase="warming"
      busy
      onReset={onReset}
      phaseLabel={phase => phase}
    />,
  );
  const button = screen.getByRole('button', { name: 'Reset ASR resources' });
  expect(button).toBeDisabled();
  expect(screen.getByRole('status')).toHaveTextContent('warming');
});
```

Test confirmation callback, keyboard activation, error recovery, `aria-live`,
44 px target, spinner, and reduced-motion class.

- [ ] **Step 3: Run frontend tests and verify RED**

Run:

```bash
cd frontend/realtime
npm test -- src/components/ResourceReset.test.tsx
```

Expected: module import fails because the component does not exist.

- [ ] **Step 4: Implement typed resource API**

Export:

```typescript
export type ResourceProfile = 'asr_only' | 'tts_only' | 'full_pipeline';
export type ResourcePhase =
  | 'queued' | 'draining' | 'releasing' | 'starting' | 'warming'
  | 'ready' | 'failed' | 'rolled_back' | 'cancelled';

export async function reconcileResources(profile: ResourceProfile) {
  return requestOperation('/api/v1/resources/reconcile', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ profile }),
  });
}

export async function resetResource(workload: 'asr' | 'tts') {
  return requestOperation(`/api/v1/resources/${workload}/reset`, {
    method: 'POST',
  });
}

export async function waitForResourceOperation(
  id: string,
  options: PollOptions = {},
): Promise<ResourceOperation> {
  const {
    fetcher = fetch,
    intervalMs = 500,
    timeoutMs = 420_000,
    onPhase = () => undefined,
  } = options;
  const deadline = performance.now() + timeoutMs;
  let delayMs = intervalMs;
  while (performance.now() < deadline) {
    try {
      const operation = await fetchResourceOperation(id, fetcher);
      onPhase(operation.phase);
      if (TERMINAL_PHASES.has(operation.phase)) return operation;
      delayMs = intervalMs;
    } catch (cause) {
      if (cause instanceof ResourceApiError && cause.status < 500) throw cause;
      delayMs = Math.min(2_000, Math.max(intervalMs, delayMs * 2));
    }
    await new Promise(resolve => globalThis.setTimeout(resolve, delayMs));
  }
  throw new ResourceApiError(
    'resource_operation_timeout',
    504,
    'Resource operation timed out',
  );
}
```

The polling loop retries network errors and 502/503 with capped 500–2,000 ms
backoff, but immediately returns typed 4xx errors. Default timeout is seven
minutes.

- [ ] **Step 5: Implement the shared control and styles**

Use a Lucide `RefreshCw` icon, secondary glass button, pressed scale, and
spinner rotation. Render textual phase and error recovery; never rely on color
alone. Disable while busy. Respect `prefers-reduced-motion`. Do not add a modal:
the parent page supplies an async `confirmReset()` so each audio state machine
can decide whether confirmation is required.

- [ ] **Step 6: Run the shared frontend tests**

Run:

```bash
cd frontend/realtime
npm test -- src/components/ResourceReset.test.tsx
```

Expected: all pass.

- [ ] **Step 7: Commit the shared UI primitive**

```bash
git add frontend/realtime/src/resources.ts \
  frontend/realtime/src/components/ResourceReset.tsx \
  frontend/realtime/src/components/ResourceReset.test.tsx \
  frontend/realtime/src/styles.css frontend/realtime/src/ttsClone/styles.css
git commit -m "feat: add shared inference resource reset control"
```

### Task 8: Integrate reset and persistent selectors into ASR Realtime

**Files:**
- Modify: `frontend/realtime/src/App.tsx`
- Modify: `frontend/realtime/src/App.test.tsx`
- Modify: `frontend/realtime/src/components/ActiveModels.tsx`
- Modify: `frontend/realtime/src/i18n.tsx`
- Modify: `frontend/realtime/src/i18n.test.tsx`

- [ ] **Step 1: Write failing ASR reset tests**

```tsx
test('resets ASR and restores the catalog after ready', async () => {
  mockResourceFlow('asr', ['draining', 'starting', 'warming', 'ready']);
  renderRealtime();
  fireEvent.click(screen.getByRole('button', { name: 'Reset ASR resources' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    '/api/v1/resources/asr/reset',
    { method: 'POST' },
  ));
  await waitFor(() => expect(fetchModelCatalog).toHaveBeenCalled());
  expect(screen.getByLabelText('ASR model')).toHaveValue('qwen3-asr-1.7b');
});


test('keeps all pinned ASR choices visible while worker is stopped', async () => {
  mockCatalog({ active: { state: 'unavailable', asr_model: null } });
  renderRealtime();
  const select = await screen.findByLabelText('ASR model');
  expect(within(select).getAllByRole('option')).toHaveLength(3);
  expect(select).toBeDisabled();
});
```

Also test: active session confirmation, client stop before reconcile, completed
transcripts preserved, partial transcript cleared, model switch disabled during
operation, temporary Gateway errors shown as reconnecting, failed operation
shows recovery hint, and no device check/listening starts.

- [ ] **Step 2: Run ASR UI tests and verify RED**

Run:

```bash
cd frontend/realtime
npm test -- src/App.test.tsx src/i18n.test.tsx
```

Expected: reset button is missing and unavailable catalog currently loses UI
readiness.

- [ ] **Step 3: Add the ASR resource state machine**

Add `resourceBusy`, `resourcePhase`, and `resourceError`. `resetResources()`:

```typescript
const resetResources = async () => {
  if (resourceBusy) return;
  if (active && !window.confirm(t('resources.confirmActive'))) return;
  setResourceBusy(true);
  setResourceError('');
  try {
    if (active) {
      await clientRef.current?.stop('resource-reset');
      setActive(false);
      dispatch({ type: 'client.model_switched' });
    }
    const accepted = await resetResource('asr');
    const result = await waitForResourceOperation(
      accepted.id,
      { onPhase: phase => setResourcePhase(phase) },
    );
    if (result.phase !== 'ready') {
      throw new ResourceApiError(
        result.errorCode ?? 'resource_operation_failed',
        503,
        result.operatorHint ?? t('resources.failed'),
      );
    }
    const catalog = await fetchModelCatalog();
    setModelCatalog(catalog);
    setAsrModel(catalog.active.requested_asr_model ?? catalog.active.asr_model
      ?? 'qwen3-asr-1.7b');
    setCorrectionModel(catalog.active.correction_model);
    await refreshCapabilities();
  } catch (cause) {
    setResourceError(resourceErrorMessage(cause));
  } finally {
    setResourceBusy(false);
  }
};
```

Do not restart listening automatically. Extract the existing one-shot
capabilities fetch into `refreshCapabilities()`.

- [ ] **Step 4: Keep selectors structurally present**

`ActiveModels` always renders the manifest choices from `ModelCatalog`. Disable
selectors when active state is unavailable, switching, or resourceBusy. Use the
requested/active fallback already defined in `deriveModelPresentation`; do not
replace the select with an empty state.

- [ ] **Step 5: Add all four ASR locale strings**

Add exact keys for reset label, confirmation, phases, reconnecting, success,
failure, and recovery in `en`, `zh-TW`, `ja`, and `ko`. Extend catalog parity
tests so every locale has the same keys.

- [ ] **Step 6: Run ASR frontend tests**

Run:

```bash
cd frontend/realtime
npm test -- src/App.test.tsx src/i18n.test.tsx \
  src/modelPresentation.test.ts
```

Expected: all pass.

- [ ] **Step 7: Commit ASR integration**

```bash
git add frontend/realtime/src/App.tsx frontend/realtime/src/App.test.tsx \
  frontend/realtime/src/components/ActiveModels.tsx \
  frontend/realtime/src/i18n.tsx frontend/realtime/src/i18n.test.tsx
git commit -m "feat: reset and restore ASR resources from realtime UI"
```

### Task 9: Integrate reset into TTS Clone Test

**Files:**
- Modify: `frontend/realtime/src/ttsClone/App.tsx`
- Modify: `frontend/realtime/src/ttsClone/App.test.tsx`
- Modify: `frontend/realtime/src/ttsClone/i18n.tsx`
- Modify: `frontend/realtime/src/ttsClone/i18n.test.tsx`
- Modify: `frontend/realtime/src/ttsClone/api.ts`

- [ ] **Step 1: Write failing TTS reset tests**

```tsx
test('resets TTS and enables controls only after worker readiness', async () => {
  const deps = cloneDeps({
    resourcePhases: ['releasing', 'starting', 'warming', 'ready'],
    statuses: [loadingCloneStatus(), readyCloneStatus()],
  });
  render(<App dependencies={deps} />);
  fireEvent.click(screen.getByRole('button', { name: 'Reset TTS resources' }));
  await waitFor(() => expect(deps.resetResource).toHaveBeenCalledWith('tts'));
  expect(screen.getByRole('button', { name: 'Start recording' })).toBeDisabled();
  await waitFor(() => expect(screen.getByText('Ready')).toBeVisible());
  fireEvent.click(screen.getByRole('button', { name: 'Check devices' }));
  await waitFor(() => expect(
    screen.getByRole('button', { name: 'Start recording' })
  ).toBeEnabled());
});
```

Also test confirmation while recording/generating/playing; reset calls
recorder stop/discard or playback stop only after confirmation; browser
reference remains when idle; Generate/Play never starts automatically; failure
preserves text/reference and shows recovery.

- [ ] **Step 2: Run TTS UI tests and verify RED**

Run:

```bash
cd frontend/realtime
npm test -- src/ttsClone/App.test.tsx src/ttsClone/i18n.test.tsx
```

Expected: reset button and dependency methods are missing.

- [ ] **Step 3: Add resource dependencies and TTS reset flow**

Extend `CloneStudioDependencies` with:

```typescript
resetResource(workload: 'tts'): Promise<ResourceOperation>;
waitForResourceOperation(
  id: string,
  onPhase: (phase: ResourcePhase) => void,
): Promise<ResourceOperation>;
```

`resetResources()` confirms only when recording, generating, or playing. After
confirmation it stops/discards the active operation, resets/ensures `tts`,
polls phases, then calls `getStatus()` until `ready`. The production dependency
calls `POST /api/v1/resources/tts/reset`. It does not run
`checkDevices()`, generate speech, or play audio. Keep `audioStore` intact when
idle; preserve typed text and style cues in every case.

- [ ] **Step 4: Add all four TTS locale strings**

Add reset label, active-operation warning, every phase, reconnecting, ready,
failed, and recovery strings to all catalogs. Extend exact-key parity tests.

- [ ] **Step 5: Run TTS frontend tests**

Run:

```bash
cd frontend/realtime
npm test -- src/ttsClone/App.test.tsx src/ttsClone/i18n.test.tsx \
  src/ttsClone/api.test.ts
```

Expected: all pass.

- [ ] **Step 6: Commit TTS integration**

```bash
git add frontend/realtime/src/ttsClone/App.tsx \
  frontend/realtime/src/ttsClone/App.test.tsx \
  frontend/realtime/src/ttsClone/i18n.tsx \
  frontend/realtime/src/ttsClone/i18n.test.tsx \
  frontend/realtime/src/ttsClone/api.ts
git commit -m "feat: reset TTS resources from clone studio"
```

### Task 10: Localize OpenAPI and document operations

**Files:**
- Modify: `src/agent_speak/locales.py`
- Modify: `tests/test_docs.py`
- Modify: `tests/test_app.py`
- Modify: `README.md`
- Modify: `spec/API.md`
- Modify: `spec/ARCHITECTURE.md`
- Modify: `spec/RUNTIME.md`
- Modify: `spec/TESTING.md`
- Modify: `spec/UI.md`
- Modify: `spec/project_herness.md`

- [ ] **Step 1: Write failing four-locale OpenAPI tests**

For each `en`, `zh-TW`, `ja`, and `ko`, assert localized summaries and
descriptions for:

```text
GET  /api/v1/resources
POST /api/v1/resources/reconcile
POST /api/v1/resources/{workload}/reset
GET  /api/v1/resource-operations/{operation_id}
```

Assert every property in resource request/response schemas has a non-empty
localized description and stable schema/property identifiers across locales.

- [ ] **Step 2: Run docs tests and verify RED**

Run:

```bash
python -m pytest tests/test_docs.py tests/test_app.py -q
```

Expected: localized resource operations or fields are absent.

- [ ] **Step 3: Add complete OpenAPI localization**

Register all four operation keys in `PATH_TEXT`, the `resources` tag in tag
metadata, and every resource schema field in `SCHEMA_FIELD_TEXT`. Keep technical
enums unchanged. Examples use `asr_only`, `tts_only`, `exclusive`, and opaque
IDs shaped like `op_6f57d9d8567b4fb5` only.

- [ ] **Step 4: Update operator and architecture documentation**

Document:

- supervisor start/stop and ignored runtime files;
- policy/profile configuration and conservative memory budgets;
- stable Gateway during reconciliation;
- reset UI behavior and explicit audio consent;
- ASR selector persistence;
- status → resource operation → per-worker logs troubleshooting;
- current `exclusive` host and future `concurrent`/`multi_gpu`;
- `full_pipeline` reserved until a real Agent provider exists.

Do not claim concurrent or multi-GPU hardware acceptance unless executed.

- [ ] **Step 5: Run docs and privacy checks**

Run:

```bash
python -m pytest tests/test_docs.py tests/test_app.py \
  tests/test_diagnostic_logging.py -q
git diff --check
```

Expected: all pass and no whitespace errors.

- [ ] **Step 6: Commit localization and docs**

```bash
git add src/agent_speak/locales.py tests/test_docs.py tests/test_app.py \
  README.md spec/API.md spec/ARCHITECTURE.md spec/RUNTIME.md \
  spec/TESTING.md spec/UI.md spec/project_herness.md
git commit -m "docs: document resource orchestration controls"
```

### Task 11: Full regression and real exclusive GPU smoke

**Files:**
- Verification only; no source file is scheduled for modification in this
  task.

- [ ] **Step 1: Rebuild test images**

Run:

```bash
docker compose build gateway-test frontend-test
```

Expected: both images build successfully from the current source.

- [ ] **Step 2: Run the complete hardware-free suite**

Run:

```bash
AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test
```

Expected: every Python, recorder-core, and Vitest test passes and prints
`TESTS_OK`.

- [ ] **Step 3: Verify the cached model manifest**

Run:

```bash
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --models
```

Expected: all pinned models verify as cached; no unexpected download begins.

- [ ] **Step 4: Exercise ASR-to-TTS from the public API**

Start ASR:

```bash
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --asr-up
curl -fsS http://127.0.0.1:8765/api/v1/resources
```

Expected: Gateway healthy, resolved policy `exclusive`, profile `asr_only`,
ASR/correction ready, TTS stopped. Record the Gateway container ID.

Reset/ensure TTS through the same endpoint used by the page:

```bash
curl -fsS -X POST \
  http://127.0.0.1:8765/api/v1/resources/tts/reset
```

Poll the returned opaque operation ID until `ready`. Confirm the Gateway
container ID is unchanged, ASR/correction stopped, TTS healthy, and
`GET /api/v1/tts-clone/status` returns `ready=true`.

- [ ] **Step 5: Exercise TTS-to-ASR and selector restoration**

Reset/ensure ASR, poll to `ready`, and confirm:

```bash
curl -fsS -X POST \
  http://127.0.0.1:8765/api/v1/resources/asr/reset
curl -fsS http://127.0.0.1:8765/api/v1/models
```

Expected: all three ASR options exist, the active/requested row is synchronized,
ASR/correction healthy, TTS stopped, and Gateway container ID remains unchanged.

- [ ] **Step 6: Browser smoke without audio permission**

Use headless Chrome to open both pages. On each page:

- confirm the reset button is visible in English;
- switch to Traditional Chinese, Japanese, and Korean and confirm its label;
- trigger reset only while no audio activity exists;
- observe staged progress and Ready;
- confirm ASR selectors never disappear;
- confirm no `getUserMedia`, recording, synthesis, or playback occurred;
- confirm zero browser console errors.

- [ ] **Step 7: Audit logs and tracked files**

Run:

```bash
./run.sh --logs gateway
./run.sh --logs asr-worker
./run.sh --logs tts-worker
git ls-files | rg '(^|/)(models|runtime|data|logs)(/|$)|\.(wav|mp3|flac|ogg)$|(^|/)\.env$'
git diff --check
git status -sb
df -h /
```

Expected: logs contain operation IDs/stages only; no audio, text, device labels,
commands, credentials, raw session IDs, or exception strings. No private path
is tracked. Only known user-owned untracked paths remain.

- [ ] **Step 8: Finish in the user's selected profile**

If the user is actively testing TTS, leave `tts_only` ready. Otherwise restore:

```bash
AGENT_SPEAK_ACCELERATOR=auto ./run.sh --asr-up
```

Report the active profile, URLs, test counts, GPU smoke evidence, disk headroom,
commits, and whether changes are pushed.

## Deferred hardware acceptance

Do not simulate these claims on the current 11 GB host:

- `concurrent`: run on a high-VRAM GPU and prove ASR and TTS stay healthy
  together while a single-worker reset leaves its peer ready.
- `multi_gpu`: configure explicit per-workload device IDs on a multi-GPU host
  and prove placement through container environment plus runtime telemetry.
- `full_pipeline`: add only after a real non-development Agent provider has its
  own design, contract, privacy review, and tests.
