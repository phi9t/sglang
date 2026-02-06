# Zephyr/MLSys Dual-Kit Workflow for `sglang`

This repository uses two complementary kits:

1. `.sygaldry/zephyr`
2. `.codex-zephyr-mlsys`

They are intentionally separate. Do not merge their configs or scripts.

## Ownership and Purpose

`/.sygaldry/zephyr`

- Primary repo-scoped container workflow.
- Provides `repoctl` and `jobctl`.
- Uses `infra.yaml` for pinned image and launch policy.
- Runs container-level verification (`verify image`, `verify spack`, `verify uv-layering`).

`/.codex-zephyr-mlsys`

- Standalone MLSys runtime kit installed by `zephyr-mlsys-env`.
- Provides `launch-mlsys.sh` plus `uv-env-build.sh` and `uv-env-validate.sh`.
- Uses `runtime.yaml` with digest-pinned `snapshot_ref`.
- Builds hermetic uv overlays by environment profile (`hf-transformers`, `sglang`, `vllm`, etc.).

## Required Invariants

1. `.sygaldry/zephyr/infra.yaml:image_ref` is digest-pinned (`@sha256:<64hex>`).
2. `.sygaldry/zephyr/infra.yaml:base_image_ref` is digest-pinned.
3. `.codex-zephyr-mlsys/runtime.yaml:snapshot_ref` is digest-pinned.
4. `image_ref` and `snapshot_ref` should match unless a deliberate split is documented.

## Core Commands

From repo root:

```bash
# Inspect active image resolution
.sygaldry/zephyr/bin/repoctl config show --repo .

# Verify image contract and Spack environment
ZEPHYR_LEASE_MODE=off .sygaldry/zephyr/bin/repoctl verify image --repo .
ZEPHYR_LEASE_MODE=off .sygaldry/zephyr/bin/repoctl verify spack --repo .

# Verify UV layering policy (strict GPU path)
.sygaldry/zephyr/bin/repoctl verify uv-layering

# Optional: keep T8.7 bounded while preserving strict GPU checks
IMAGE_REF="$(awk -F': ' '/^image_ref:/{print $2}' .sygaldry/zephyr/infra.yaml)"
.sygaldry/zephyr/container/verify_uv_layering.sh \
  "${IMAGE_REF}" \
  --datasets-timeout-sec 180

# Build a standalone MLSys env from the codex kit
.codex-zephyr-mlsys/bin/launch-mlsys.sh sglang --no-validate
```

## Full Validation Runner

Use the repo validation script to run dual-kit checks and capture logs:

```bash
./scripts/validate_zephyr_dual_kit.sh --repo .

# Optional timeout tuning for long runs
UV_LAYERING_TIMEOUT_SEC=7200 \
UV_LAYERING_DATASETS_TIMEOUT_SEC=600 \
CROSSKIT_TIMEOUT_SEC=900 \
CODEX_BUILD_TIMEOUT_SEC=7200 \
./scripts/validate_zephyr_dual_kit.sh --repo .
```

Outputs are written to `artifacts/dual_kit_validation_<timestamp>/`.

## Troubleshooting

1. Strict policy: do not use `--no-gpu` or `MLSYS_DISABLE_GPU=1` in this repo.
2. If launcher commands stall, check stale containers and lease contention under `/mnt/data_infra/zephyr_container_infra/projects/sglang/`.
3. For lease-related contention, rerun with `ZEPHYR_LEASE_MODE=off`.
4. If `verify uv-layering` is slow on T8.7 datasets stage, increase `UV_LAYERING_DATASETS_TIMEOUT_SEC` (validation script) or pass `--datasets-timeout-sec` directly and review log tail.
