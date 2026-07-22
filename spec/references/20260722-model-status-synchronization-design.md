# Realtime model status synchronization

## Problem

The model selectors store the requested ASR and correction models, while the
worker detail rows render the previous `active.asr_model` and static provider
capabilities. During an asynchronous ASR switch this makes the selector and the
detail rows disagree, and correction selection can remain stale indefinitely.

## Display contract

The model control has two explicit truths:

- **Target selection:** the model requested by the user. The selector and model
  detail row show this value immediately.
- **Runtime readiness:** the model reported by `/api/v1/models`. A model is only
  shown as Ready when `state === "ready"`, `active.asr_model` equals the target,
  and no requested ASR model remains.

While switching, the target ASR name is paired with a spinner and the worker
lifecycle returned by the catalog (`unloading`, `loading`, `warming`, or
`rollback`). The correction detail row uses the selected correction model and
its catalog label instead of the static capabilities response. Device labels
continue to come from runtime truth.

If activation fails, the selectors and detail rows roll back together to the
last catalog-confirmed active ASR and correction models. The error remains
visible and the lifecycle is Failed or Unavailable; the UI must never show the
failed target as Ready.

## Boundaries

This is a presentation-state fix. It does not change `/api/v1`, worker loading,
model leasing, audio capture, or session contracts. Microphone and speaker
activation remain user-gated.

## Verification

Frontend tests simulate the complete old-model → switching → new-model-ready
sequence and assert that selectors, detail rows, spinner, and Ready indicator
remain synchronized. A failure test asserts rollback to runtime truth. The
standard Docker test suite and production frontend build remain the final gate.

