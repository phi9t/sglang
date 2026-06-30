#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[XENO] Activating torch-jax-ffmpeg Spack environment..." >&2
. "$HOME/spack/share/spack/setup-env.sh"
spack env activate torch-jax-ffmpeg

echo "[XENO] Running JAX GPU test..." >&2
python "$ROOT_DIR/test_jax_gpu.py"

echo "[XENO] Running PyTorch GPU + NCCL/distributed test..." >&2
python "$ROOT_DIR/test_torch_gpu_nccl.py"

echo "[XENO] Running FFmpeg codec tests..." >&2
"$ROOT_DIR/test_ffmpeg_codecs.sh"

echo "[XENO] All tests completed successfully." >&2

