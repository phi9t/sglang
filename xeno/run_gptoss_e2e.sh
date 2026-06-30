#!/usr/bin/env bash
#
# End-to-end smoke test: bring up GPT-OSS via the Xeno compose stack, verify
# /health and a minimal OpenAI-compatible chat completion, then tear down.
#
# Prerequisites: Docker with Compose v2.23+ (`include`), NVIDIA Container Toolkit,
# enough GPUs/vRAM for openai/gpt-oss-120b at your chosen TP (see compose file).
#
# Usage:
#   ./xeno/run_gptoss_e2e.sh
#
# Environment (optional):
#   HOST_PORT, MODEL_PATH, IMAGE, CONTAINER_NAME, HF_CACHE_DIR, TP, HF_TOKEN
#   GPTOSS_E2E_SKIP_PULL=1   Skip docker compose pull (faster reruns)
#   GPTOSS_E2E_SKIP_DOWN=1  Leave the stack running after the test
#   GPTOSS_E2E_COMPOSE_FILE Override compose file (default: docker/compose.xeno.yaml)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_REL="${GPTOSS_E2E_COMPOSE_FILE:-${REPO_ROOT}/docker/compose.xeno.yaml}"
if [[ ! -f "${COMPOSE_REL}" ]]; then
  echo "[e2e] Compose file not found: ${COMPOSE_REL}" >&2
  exit 1
fi

IMAGE="${IMAGE:-lmsysorg/sglang:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-sglang-gptoss-120b-test}"
MODEL_PATH="${MODEL_PATH:-openai/gpt-oss-120b}"
HOST_PORT="${HOST_PORT:-30000}"
HF_CACHE_DIR="${HF_CACHE_DIR:-$HOME/sglang-hf-cache}"

HEALTH_URL="http://127.0.0.1:${HOST_PORT}/health"
GEN_URL="http://127.0.0.1:${HOST_PORT}/v1/chat/completions"

export IMAGE CONTAINER_NAME MODEL_PATH HOST_PORT HF_CACHE_DIR TP HF_TOKEN

compose() {
  docker compose -f "${COMPOSE_REL}" "$@"
}

cleanup() {
  if [[ "${GPTOSS_E2E_SKIP_DOWN:-}" == "1" ]]; then
    echo "[e2e] GPTOSS_E2E_SKIP_DOWN=1 — leaving compose stack running." >&2
    return 0
  fi
  echo "[e2e] Bringing stack down..." >&2
  compose down --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

if ! command -v docker >/dev/null 2>&1; then
  echo "[e2e] docker not found in PATH" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "[e2e] docker compose plugin required" >&2
  exit 1
fi

mkdir -p "${HF_CACHE_DIR}"

SGLANG_UID="$(id -u)"
SGLANG_GID="$(id -g)"
export SGLANG_UID SGLANG_GID

echo "[e2e] Compose file: ${COMPOSE_REL}" >&2
if ! compose config >/dev/null 2>&1; then
  echo "[e2e] 'docker compose config' failed — need Compose v2.23+ with include support," >&2
  echo "      or set GPTOSS_E2E_COMPOSE_FILE=${REPO_ROOT}/docker/compose.gptoss_gsm8k.yaml" >&2
  exit 1
fi

echo "[e2e] Stopping any previous stack for this project..." >&2
compose down --remove-orphans >/dev/null 2>&1 || true

if [[ "${GPTOSS_E2E_SKIP_PULL:-}" != "1" ]]; then
  echo "[e2e] Pulling images..." >&2
  compose pull
else
  echo "[e2e] Skipping pull (GPTOSS_E2E_SKIP_PULL=1)" >&2
fi

echo "[e2e] Starting stack..." >&2
compose up -d

echo "[e2e] Waiting for ${HEALTH_URL} ..." >&2
ok=0
for i in $(seq 1 120); do
  if curl -fsS --max-time 5 "${HEALTH_URL}" >/dev/null 2>&1; then
    ok=1
    echo "[e2e] Healthy after attempt ${i}" >&2
    break
  fi
  sleep 10
done
if [[ "${ok}" -ne 1 ]]; then
  echo "[e2e] Server did not become healthy in time" >&2
  compose logs --tail 120 >&2 || true
  exit 1
fi

echo "[e2e] POST ${GEN_URL} (minimal chat completion)..." >&2
payload="$(MODEL_PATH="${MODEL_PATH}" python3 - <<'PY'
import json, os
print(json.dumps({
    "model": os.environ["MODEL_PATH"],
    "messages": [{"role": "user", "content": "Reply with one word: OK."}],
    "max_tokens": 16,
    "temperature": 0,
}))
PY
)"

response="$(curl -fsS --max-time 600 "${GEN_URL}" \
  -H "Content-Type: application/json" \
  -d "${payload}")" || {
  echo "[e2e] Chat completion request failed" >&2
  exit 1
}

echo "${response}" | python3 - <<'PY'
import json, sys
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print("invalid JSON:", e, file=sys.stderr)
    sys.exit(1)
choices = data.get("choices") or []
if not choices:
    print("no choices in response:", raw[:500], file=sys.stderr)
    sys.exit(1)
msg = (choices[0].get("message") or {}).get("content") or ""
print("[e2e] completion preview:", repr(msg[:200]))
PY

echo "[e2e] PASS — GPT-OSS stack responded with a valid chat completion." >&2
