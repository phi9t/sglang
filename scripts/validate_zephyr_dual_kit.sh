#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  validate_zephyr_dual_kit.sh [--repo <path>] [--skip-uv-layering] [--skip-mlsys-build] [--mlsys-env <name>]

Options:
  --repo <path>         Target repository root (default: git root of current directory)
  --skip-uv-layering    Skip repoctl UV layering verification
  --skip-mlsys-build    Skip launch-mlsys build smoke test
  --mlsys-env <name>    Env to build via launch-mlsys (default: sglang)
USAGE
}

log() {
    echo "[validate-zephyr-dual-kit] $*" >&2
}

die() {
    log "ERROR: $*"
    exit 1
}

yaml_value() {
    local file="$1"
    local key="$2"
    awk -F ':' -v want="${key}" '
        $0 ~ "^[[:space:]]*" want "[[:space:]]*:[[:space:]]*" {
            sub("^[[:space:]]*" want "[[:space:]]*:[[:space:]]*", "", $0)
            sub(/[[:space:]]+#.*/, "", $0)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
            gsub(/^"|"$/, "", $0)
            print $0
            exit
        }
    ' "${file}"
}

require_digest_ref() {
    local ref="$1"
    [[ -n "${ref}" ]] || die "digest ref is empty"
    [[ "${ref}" == *@sha256:* ]] || die "ref must include @sha256: ${ref}"
    local digest
    digest="${ref##*@sha256:}"
    [[ "${digest}" =~ ^[a-f0-9]{64}$ ]] || die "invalid digest format: ${digest}"
}

run_step() {
    local step="$1"
    shift 1

    local log_file="${ARTIFACT_DIR}/${step}.log"
    log "Running step '${step}'"
    {
        echo "# step=${step}"
        echo "# cmd=$*"
        echo "# started_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        echo
    } > "${log_file}"

    set +e
    "$@" >> "${log_file}" 2>&1
    local rc=$?
    set -e

    if [[ ${rc} -eq 0 ]]; then
        log "PASS: ${step}"
        PASSED_STEPS+=("${step}")
        return 0
    fi

    log "FAIL: ${step} (exit ${rc})"
    FAILED_STEPS+=("${step}")
    return 1
}

record_step() {
    run_step "$@" || true
}

REPO_ROOT=""
SKIP_UV_LAYERING=0
SKIP_MLSYS_BUILD=0
MLSYS_ENV="sglang"
UV_LAYERING_TIMEOUT_SEC="${UV_LAYERING_TIMEOUT_SEC:-2400}"
UV_LAYERING_DATASETS_TIMEOUT_SEC="${UV_LAYERING_DATASETS_TIMEOUT_SEC:-600}"
CROSSKIT_TIMEOUT_SEC="${CROSSKIT_TIMEOUT_SEC:-300}"
CODEX_BUILD_TIMEOUT_SEC="${CODEX_BUILD_TIMEOUT_SEC:-2400}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            REPO_ROOT="${2:-}"
            shift 2
            ;;
        --skip-uv-layering)
            SKIP_UV_LAYERING=1
            shift
            ;;
        --skip-mlsys-build)
            SKIP_MLSYS_BUILD=1
            shift
            ;;
        --mlsys-env)
            MLSYS_ENV="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

if [[ -z "${REPO_ROOT}" ]]; then
    if command -v git >/dev/null 2>&1; then
        REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    else
        REPO_ROOT="$(pwd)"
    fi
fi

REPO_ROOT="$(realpath "${REPO_ROOT}")"
[[ -d "${REPO_ROOT}" ]] || die "repo root not found: ${REPO_ROOT}"

SYGALDRY_KIT="${REPO_ROOT}/.sygaldry/zephyr"
CODEX_KIT="${REPO_ROOT}/.codex-zephyr-mlsys"
SYGALDRY_INFRA="${SYGALDRY_KIT}/infra.yaml"
CODEX_RUNTIME="${CODEX_KIT}/runtime.yaml"

[[ -x "${SYGALDRY_KIT}/bin/repoctl" ]] || die "missing repoctl: ${SYGALDRY_KIT}/bin/repoctl"
[[ -f "${SYGALDRY_INFRA}" ]] || die "missing infra config: ${SYGALDRY_INFRA}"
[[ -x "${CODEX_KIT}/bin/launch-mlsys.sh" ]] || die "missing launch-mlsys: ${CODEX_KIT}/bin/launch-mlsys.sh"
[[ -f "${CODEX_RUNTIME}" ]] || die "missing runtime config: ${CODEX_RUNTIME}"

SYGALDRY_IMAGE_REF="$(yaml_value "${SYGALDRY_INFRA}" image_ref)"
SYGALDRY_BASE_REF="$(yaml_value "${SYGALDRY_INFRA}" base_image_ref)"
CODEX_SNAPSHOT_REF="$(yaml_value "${CODEX_RUNTIME}" snapshot_ref)"

require_digest_ref "${SYGALDRY_IMAGE_REF}"
require_digest_ref "${SYGALDRY_BASE_REF}"
require_digest_ref "${CODEX_SNAPSHOT_REF}"

if [[ "${SYGALDRY_IMAGE_REF}" != "${CODEX_SNAPSHOT_REF}" ]]; then
    die "digest mismatch: infra image_ref != codex snapshot_ref"
fi

if [[ "${SYGALDRY_IMAGE_REF}" != "${SYGALDRY_BASE_REF}" ]]; then
    log "WARNING: image_ref and base_image_ref differ in .sygaldry/zephyr/infra.yaml"
fi

ARTIFACT_PARENT="${REPO_ROOT}/artifacts"
mkdir -p "${ARTIFACT_PARENT}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_DIR="${ARTIFACT_PARENT}/dual_kit_validation_${TS}"
mkdir -p "${ARTIFACT_DIR}"

PASSED_STEPS=()
FAILED_STEPS=()
WARNINGS=()

{
    echo "repo_root=${REPO_ROOT}"
    echo "timestamp_utc=${TS}"
    echo "gpu_mode=strict"
    echo "skip_uv_layering=${SKIP_UV_LAYERING}"
    echo "skip_mlsys_build=${SKIP_MLSYS_BUILD}"
    echo "mlsys_env=${MLSYS_ENV}"
    echo "uv_layering_timeout_sec=${UV_LAYERING_TIMEOUT_SEC}"
    echo "uv_layering_datasets_timeout_sec=${UV_LAYERING_DATASETS_TIMEOUT_SEC}"
    echo "crosskit_timeout_sec=${CROSSKIT_TIMEOUT_SEC}"
    echo "codex_build_timeout_sec=${CODEX_BUILD_TIMEOUT_SEC}"
    echo "sygaldry_image_ref=${SYGALDRY_IMAGE_REF}"
    echo "sygaldry_base_ref=${SYGALDRY_BASE_REF}"
    echo "codex_snapshot_ref=${CODEX_SNAPSHOT_REF}"
} > "${ARTIFACT_DIR}/context.txt"

record_step "repoctl_config_show" \
    "${SYGALDRY_KIT}/bin/repoctl" config show --repo "${REPO_ROOT}"

record_step "repoctl_verify_image_skip_spack" \
    env ZEPHYR_LEASE_MODE=off "${SYGALDRY_KIT}/bin/repoctl" verify image --skip-spack --repo "${REPO_ROOT}"

record_step "repoctl_verify_spack" \
    env ZEPHYR_LEASE_MODE=off "${SYGALDRY_KIT}/bin/repoctl" verify spack --repo "${REPO_ROOT}"

if [[ ${SKIP_UV_LAYERING} -eq 0 ]]; then
    record_step "repoctl_verify_uv_layering" \
        timeout "${UV_LAYERING_TIMEOUT_SEC}" \
        "${SYGALDRY_KIT}/bin/repoctl" verify uv-layering --datasets-timeout-sec "${UV_LAYERING_DATASETS_TIMEOUT_SEC}"
else
    log "Skipping UV layering verification (--skip-uv-layering)"
fi

record_step "crosskit_repoctl_import_smoke" \
    timeout "${CROSSKIT_TIMEOUT_SEC}" \
    env ZEPHYR_LEASE_MODE=off SYGALDRY_FORCE_NONINTERACTIVE=1 "${SYGALDRY_KIT}/bin/repoctl" run --repo "${REPO_ROOT}" -- \
    python -c "import sglang, torch; assert torch.cuda.is_available(); print(sglang.__file__); print(torch.__version__); print(torch.cuda.is_available())"

if [[ ${SKIP_MLSYS_BUILD} -eq 0 ]]; then
    record_step "codex_launch_mlsys_build" \
        timeout "${CODEX_BUILD_TIMEOUT_SEC}" \
        "${CODEX_KIT}/bin/launch-mlsys.sh" "${MLSYS_ENV}" --no-validate
else
    log "Skipping launch-mlsys build (--skip-mlsys-build)"
fi

SUMMARY="${ARTIFACT_DIR}/summary.txt"
{
    echo "validation_dir=${ARTIFACT_DIR}"
    echo "passed_steps=${#PASSED_STEPS[@]}"
    for s in "${PASSED_STEPS[@]}"; do
        echo "PASS ${s}"
    done
    echo "failed_steps=${#FAILED_STEPS[@]}"
    for s in "${FAILED_STEPS[@]}"; do
        echo "FAIL ${s}"
    done
    echo "warnings=${#WARNINGS[@]}"
    for w in "${WARNINGS[@]}"; do
        echo "WARN ${w}"
    done
} > "${SUMMARY}"

if [[ ${#FAILED_STEPS[@]} -gt 0 ]]; then
    log "Validation finished with failures. See ${SUMMARY}"
    exit 1
fi

log "Validation finished successfully. Summary: ${SUMMARY}"
