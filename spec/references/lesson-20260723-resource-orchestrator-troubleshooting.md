# Lesson: Resource Orchestrator Runtime and Reset Troubleshooting

Date: 2026-07-23

## Summary

The Resource Orchestrator keeps the Gateway stable while ASR and TTS workers
change residency. On an exclusive GPU, reset and profile switching can take
minutes because the target model must be loaded and warmed again. Larger hosts
can keep ASR/correction and TTS resident concurrently, but a deliberate reset
still restarts the selected worker and therefore still has target warm-up time.

The first real-hardware acceptance also found a startup defect: `run.sh`
constructed every supervisor argument but omitted the required `server`
subcommand. Static/fake lifecycle tests did not exercise the daemon launch
path. Commit `b03f0ad` added the subcommand and a regression assertion.

## Applies When

- **Reset resources** stays in `releasing`, `starting`, or `warming`.
- `/api/v1/resources` returns
  `resource_supervisor_unavailable` with HTTP 503.
- `./run.sh --status` reports `resource_policy=unavailable`.
- ASR and TTS unexpectedly evict each other, or a larger GPU does not resolve
  to `concurrent`.
- Source tests pass but the running Gateway does not expose the new resource
  endpoints.

## Expected Behavior

The Gateway remains healthy and keeps the same container ID throughout worker
reconciliation. Resource operations progress through:

```text
queued → releasing → starting → warming → ready|failed|rolled_back
```

On `exclusive`, ASR/correction and TTS cannot remain resident together. On
`concurrent`, a page-level reset of a missing workload may add it without
evicting healthy peers. Exact profile commands remain exact:

- `./run.sh --asr-up` reconciles `asr_only` and may stop TTS.
- `./run.sh --tts-up` reconciles `tts_only` and may stop ASR/correction.

Do not use those exact-profile commands merely to navigate between pages on a
concurrent host. A ready worker needs no reset just because the user opened its
page.

## Capacity Planning for a 32 GB Host

With the default `.env.example` budgets, automatic concurrent residency
requires:

```text
reserve 1500
+ ASR 6500
+ correction 1000
+ TTS 9500
= 18,500 MB
```

Therefore, a 32 GB AGX Orin should theoretically resolve
`AGENT_SPEAK_RESOURCE_POLICY=auto` to `concurrent` if its NVIDIA inventory
reports at least 18,500 MB for the configured device. This has **not** yet been
verified on that hardware.

Current implementation detail: `ComposeLifecycleAdapter.usable_gpu_memory_mb()`
validates both total and free values returned by `nvidia-smi`, but policy
selection currently sums the reported **total** capacity of assigned GPUs. It
does not subtract live memory consumed by unrelated processes. Keep the reserve
and per-workload budgets conservative, inspect real device usage, and require a
cold-start hardware smoke before treating `auto → concurrent` as accepted.
Worker health and rollback remain the runtime backstop; they are not a substitute
for correct budgets.

If predictable placement is more important than automatic selection, set an
explicit policy only after hardware validation:

```dotenv
AGENT_SPEAK_RESOURCE_POLICY=concurrent
```

Never force `concurrent` merely because nominal RAM is large. Jetson unified
memory is also consumed by the OS and CPU workloads.

## Incident: Supervisor Failed to Start

### Symptoms

`./run.sh --build` built the images but ended with:

```text
ERROR: resource supervisor failed to start; inspect ./runtime/resource-control/supervisor.log
```

The log contained:

```text
resource_supervisor.py: error: the following arguments are required: mode
```

Later, the Gateway stayed healthy but returned:

```json
{
  "error": {
    "code": "resource_supervisor_unavailable",
    "stage": "resources",
    "retryable": true
  }
}
```

### Root Cause

`start_resource_supervisor()` in `run.sh` built the argv array but did not append
the `server` subcommand. Fake command tests returned a successful `client ping`,
so they skipped the real daemon-launch branch.

### Fix and Guardrail

`run.sh` now appends `command+=(server)`. The static lifecycle contract in
`tests/test_docker_runtime.py` asserts that the subcommand remains present.
When changing supervisor CLI construction, test both a responding existing
supervisor and a missing supervisor that must actually launch.

## Troubleshooting Order

Run these checks before changing resource behavior:

1. Read live truth:

   ```bash
   AGENT_SPEAK_ACCELERATOR=auto ./run.sh --status
   curl -fsS http://127.0.0.1:8765/api/v1/resources
   ```

2. If resource status is unavailable, inspect the host control plane:

   ```bash
   tail -80 runtime/resource-control/supervisor.log
   ls -ld runtime runtime/resource-control
   ls -l runtime/resource-control
   ps -ef | grep '[a]gent_speak.resource_supervisor'
   ```

   Expected permissions are a private runtime directory and Unix socket. A
   stale socket file does not prove a live supervisor; the process and
   `client ping` must both succeed.

3. Inspect the target worker without exposing prompts or audio:

   ```bash
   ./run.sh --logs asr-worker
   ./run.sh --logs tts-worker
   docker ps --filter name=agent-speak --format '{{.Names}} {{.Status}}'
   ```

4. Poll the operation returned by reset/reconcile until a terminal phase:

   ```bash
   curl -fsS \
     http://127.0.0.1:8765/api/v1/resource-operations/<operation_id>
   ```

   Do not treat a long `warming` phase as a deadlock while the worker health is
   still `starting`. VoxCPM2 cold start/reset on the accepted 11 GB-class host
   took roughly three minutes.

5. If code changed but the endpoint is missing, rebuild/recreate the Gateway:

   ```bash
   AGENT_SPEAK_ACCELERATOR=auto ./run.sh --build
   ```

   A successful source test does not update a previously running image.

6. Before modifying behavior, run:

   ```bash
   AGENT_SPEAK_ACCELERATOR=cpu ./run.sh --test
   ```

## Sandbox and Tooling Pitfalls

- A managed sandbox may prevent snap-packaged Docker or `nvidia-smi` from
  acquiring required capabilities. Errors such as
  `snap-confine ... cap_dac_override` are execution-environment evidence, not
  proof of an Agent Speak defect.
- Some task runners reclaim background children when the command exits, even
  when `nohup` is used. A supervisor that disappears only under such a runner
  must be rechecked from a normal host terminal or a maintained foreground
  process before changing daemon code.
- Localhost may be isolated inside a network sandbox. Confirm health outside
  that sandbox before claiming the Gateway is down.
- Do not infer live success from mocked Unix-socket, Docker, or GPU tests.

## Verification Baseline

The 2026-07-23 acceptance used no microphone capture, synthesis, or playback.
It verified:

- complete Docker CPU regression ending in `TESTS_OK`;
- 19 frontend test files and 86 tests passing;
- ASR reset reached `ready`;
- TTS profile cold start reached `ready`;
- TTS reset reached `ready`;
- final reconciliation returned to `asr_only` with ASR/correction ready;
- Gateway container ID remained
  `ede411e518fe8eaa85731ef2f01ef386afd0c1029deb61f21211b7d986205acb`
  throughout the accepted lifecycle sequence.

The container ID is historical evidence only and must never be used as a
future expected value. Re-record the before/after ID for each acceptance run.

## Future-Agent Checklist

1. Read `spec/PROJECT_MAP.md`, `spec/RUNTIME.md`, and this lesson.
2. Treat `./run.sh --status` and `/api/v1/resources` as live truth.
3. Distinguish page navigation, exact profile reconciliation, and deliberate
   worker reset; they have different residency effects.
4. Confirm whether the running image contains the source change.
5. Inspect supervisor process/log/socket before blaming Gateway routing.
6. On a 32 GB Orin, record actual inventory, resolved policy, peak unified
   memory, both worker health states, and Gateway ID stability.
7. Never start microphone capture, synthesis, or playback as part of resource
   troubleshooting without separate explicit user consent.

## Links

- Design: [Extensible GPU Resource Orchestrator](20260723-resource-orchestrator-design.md)
- Plan: [Resource Orchestrator Implementation Plan](20260723-resource-orchestrator-plan.md)
- Runtime: [Runtime](../RUNTIME.md)
- Testing: [Testing](../TESTING.md)
- Code: `run.sh`, `src/agent_speak/resource_supervisor.py`,
  `src/agent_speak/resource_types.py`
- Regression: `tests/test_docker_runtime.py`,
  `tests/test_resource_supervisor.py`, `tests/test_resource_types.py`
