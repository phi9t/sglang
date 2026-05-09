#!/usr/bin/env bash

# Containerized GSM8k benchmark for SGLang following foundation.org.
#
# - Runs SGLang strictly inside Docker Compose (no host Python changes).
# - Uses a dedicated host HF cache directory mounted into the container.
# - Launches an OpenAI-style SGLang server for openai/gpt-oss-120b via
#   docker compose, using docker/compose.gptoss_gsm8k.yaml.
# - Waits for server health, then runs the GSM8k evaluation script inside
#   the same container and prints summary metrics.
#
# Environment variables (optional overrides):
#   IMAGE          - SGLang Docker image (default: lmsysorg/sglang:latest)
#   CONTAINER_NAME - Docker container name (default: sglang-gptoss-120b-test)
#   MODEL_PATH     - HF model path (default: openai/gpt-oss-120b)
#   HOST_PORT      - Host port mapped to container 30000 (default: 30000)
#   HF_CACHE_DIR   - Host HF cache dir (default: $HOME/sglang-hf-cache)
#   TP             - Tensor-parallel degree (default: # of visible GPUs)
#   NUM_QUESTIONS  - Number of GSM8k questions (default: 1319)
#   PARALLEL       - Evaluation concurrency (default: 64)
#   HF_TOKEN       - HF auth token; passed through to container if set.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/compose.gptoss_gsm8k.yaml"

IMAGE=${IMAGE:-lmsysorg/sglang:latest}
CONTAINER_NAME=${CONTAINER_NAME:-sglang-gptoss-120b-test}
MODEL_PATH=${MODEL_PATH:-openai/gpt-oss-120b}
HOST_PORT=${HOST_PORT:-30000}
HF_CACHE_DIR=${HF_CACHE_DIR:-"$HOME/sglang-hf-cache"}
NUM_QUESTIONS=${NUM_QUESTIONS:-1319}
PARALLEL=${PARALLEL:-64}

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] docker not found in PATH" >&2
  exit 1
fi

# Check docker compose subcommand
if ! docker compose version >/dev/null 2>&1; then
  echo "[error] 'docker compose' subcommand is not available" >&2
  exit 1
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l | tr -d ' ')
else
  echo "[warn] nvidia-smi not found; assuming 1 GPU" >&2
  GPU_COUNT=1
fi

if [ "${GPU_COUNT}" -lt 1 ]; then
  echo "[error] No GPUs detected" >&2
  exit 1
fi

TP=${TP:-$GPU_COUNT}

echo "[info] Using image:          ${IMAGE}" >&2
echo "[info] Container name:       ${CONTAINER_NAME}" >&2
echo "[info] Model path:           ${MODEL_PATH}" >&2
echo "[info] Host port:            ${HOST_PORT}" >&2
echo "[info] HF cache dir:         ${HF_CACHE_DIR}" >&2
echo "[info] Tensor parallel (TP):  ${TP}" >&2
echo "[info] GSM8k questions:      ${NUM_QUESTIONS}" >&2
echo "[info] GSM8k parallelism:    ${PARALLEL}" >&2
echo "[info] Compose file:         ${COMPOSE_FILE}" >&2

mkdir -p "${HF_CACHE_DIR}"

if [ -z "${HF_TOKEN:-}" ]; then
  echo "[warn] HF_TOKEN not set; models requiring auth may fail to download" >&2
fi

export IMAGE CONTAINER_NAME MODEL_PATH HOST_PORT HF_CACHE_DIR TP HF_TOKEN

SGLANG_UID=$(id -u)
SGLANG_GID=$(id -g)
export SGLANG_UID SGLANG_GID

echo "[action] Bringing down any existing benchmark compose stack" >&2
docker compose -f "${COMPOSE_FILE}" down --remove-orphans >/dev/null 2>&1 || true

echo "[action] Pulling SGLang image via docker compose" >&2
docker compose -f "${COMPOSE_FILE}" pull

echo "[action] Starting SGLang server via docker compose" >&2
docker compose -f "${COMPOSE_FILE}" up -d

HEALTH_URL="http://127.0.0.1:${HOST_PORT}/health"
echo "[check] Waiting for SGLang server health at ${HEALTH_URL}" >&2

for i in $(seq 1 60); do
  if curl -fsS --max-time 5 "${HEALTH_URL}" >/dev/null 2>&1; then
    echo "[info] SGLang server is healthy (attempt ${i})" >&2
    break
  fi
  echo "[wait] Not healthy yet, retrying in 10s (attempt ${i})" >&2
  sleep 10
  if [ "${i}" -eq 60 ]; then
    echo "[error] SGLang server did not become healthy in time" >&2
    docker compose -f "${COMPOSE_FILE}" logs --tail 200 || true
    exit 1
  fi
done

echo "[action] Running GSM8k evaluation inside container" >&2
docker exec "${CONTAINER_NAME}" \
  bash -lc 'cd /tmp && python3 -m sglang.test.few_shot_gsm8k \
    --num-questions '"${NUM_QUESTIONS}"' \
    --parallel '"${PARALLEL}"' \
    --host http://127.0.0.1 \
    --port 30000'

echo "[info] GSM8k benchmark completed" >&2
echo "[info] To inspect per-example outputs (if generated), run:" >&2
echo "  mkdir -p \"$HOME/sglang-gsm8k-logs\"" >&2
echo "  docker cp ${CONTAINER_NAME}:/tmp/tmp_output_gsm8k.txt \\"$HOME/sglang-gsm8k-logs/tmp_output_gsm8k.txt\\"" >&2
