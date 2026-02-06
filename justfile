set shell := ["bash", "-euo", "pipefail", "-c"]

repo_root := justfile_directory()
venv_in_container := "/workspace/sglang/.mlsys-venvs/sglang"

default:
  @just --list

# Hard fail if CUDA runtime/container GPU path is not healthy.
verify-cuda:
  cd {{repo_root}} && ./.sygaldry/zephyr/bin/repoctl verify spack --repo "$(pwd)"

# Build the vendored MLSys sglang environment into repo-local venv storage.
build-sglang: verify-cuda
  cd {{repo_root}} && ./.codex-zephyr-mlsys/bin/launch-mlsys.sh sglang --venv-root /repo/.mlsys-venvs

# Launch Qwen3.5-0.8B with SGLang in Zephyr container runtime.
# This hard fails if CUDA is not available from the built venv.
run-qwen35 port='30000' model='Qwen/Qwen3.5-0.8B': verify-cuda
  cd {{repo_root}} && ./.sygaldry/zephyr/bin/repoctl run --repo "$(pwd)" -- bash -lc '\
  VENV={{venv_in_container}}; \
  [[ -x "$VENV/bin/python" ]] || { echo "ERROR: missing built venv at $VENV. Run: just build-sglang" >&2; exit 1; }; \
  "$VENV/bin/python" -c "import torch; assert torch.cuda.is_available(), \"ERROR: CUDA is required but not available.\"; print(\"CUDA device:\", torch.cuda.get_device_name(0))"; \
  export LD_LIBRARY_PATH=/opt/spack_store/view/lib:${LD_LIBRARY_PATH:-}; \
  exec "$VENV/bin/python" -m sglang.launch_server --model {{model}} --model-impl transformers --tp 1 --host 0.0.0.0 --port {{port}} \
  '

# Send one inference request to a running local server.
infer-qwen35 port='30000' model='Qwen/Qwen3.5-0.8B':
  cd {{repo_root}} && ./.sygaldry/zephyr/bin/repoctl run --repo "$(pwd)" -- bash -lc '\
  VENV={{venv_in_container}}; \
  [[ -x "$VENV/bin/python" ]] || { echo "ERROR: missing built venv at $VENV. Run: just build-sglang" >&2; exit 1; }; \
  "$VENV/bin/python" /workspace/sglang/examples/runtime/qwen35_0_8b_chat_inference.py --base-url http://127.0.0.1:{{port}} --model {{model}} \
  '
