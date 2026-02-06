# Rust Ferric Execution Worker Contract

This document defines the Step 2 boundary freeze for Ferric migration.

## Intent

- Rust owns infrastructure/control path: RPC ingress, async lifecycle, scheduler, radix cache.
- Python/Torch/CUDA worker owns model execution path: forward passes and kernel interactions.
- The boundary between them is a stable RPC contract in:
  - `proto/sglang/sglang_execution_worker.proto`

## Contract goals

1. Keep batch execution semantics explicit (`ExecutePrefill`, `ExecuteDecode`).
2. Preserve request-level observability and finish-reason semantics.
3. Keep payload extensible for model-specific fields via `google.protobuf.Struct extension`.
4. Support future zero-copy/IPC paths via `TensorRef`.
5. Keep API idempotent and retry-safe via `batch_id`.

## Core methods

- `ExecutePrefill(ExecuteBatchRequest) -> ExecuteBatchResponse`
  - Used for prefill/extend stage.
- `ExecuteDecode(ExecuteBatchRequest) -> ExecuteBatchResponse`
  - Used for decode stage.
- `Cancel(CancelRequest) -> CancelResponse`
  - Best-effort cancellation.
- `HealthCheck(HealthCheckRequest) -> HealthCheckResponse`
  - Health/readiness probe.
- `GetWorkerInfo(GetWorkerInfoRequest) -> GetWorkerInfoResponse`
  - Capability discovery.

## Mapping to current Python runtime concepts

- `ExecuteBatchRequest` maps to the data currently assembled near:
  - `ScheduleBatch`
  - `ModelWorkerBatch`
  in `python/sglang/srt/managers/schedule_batch.py`.

- `ExecuteBatchResponse.results[*]` maps to request output updates currently consumed by scheduler output processing.

- `num_running_reqs`, `num_waiting_reqs`, and token counters map to scheduler feedback loops for admission and load balancing.

## Invariants and semantics

1. `batch_id` is unique per execution attempt.
2. Worker treats duplicate `batch_id` as idempotent replay when possible.
3. `status` values:
   - `OK`: execution completed and `results` are valid.
   - `RETRYABLE_ERROR`: caller may retry same batch.
   - `FATAL_ERROR`: caller should fail request(s) and trigger remediation.
4. `results` is per-request and must include `request_id` for deterministic merge on Rust side.
5. `extension` fields are optional and must not break unknown-field compatibility.

## Versioning policy

- This proto is `v1` candidate for Ferric migration.
- Any breaking change requires:
  1. new method or new message field path (never field reuse),
  2. dual-version support window,
  3. parity harness validation across both versions.

## Rollout usage

1. Implement Python worker adapter against this proto (without replacing scheduler yet).
2. Implement Rust scheduler caller using same proto.
3. Run dual-run parity harness before any production canary.
