# Justfile for SGLang local workflows
#
# Python deps live under python/ — use `uv --project python` (wrapped below).
# Activate mise-managed tools: `mise install` then ensure mise shims are on PATH.

# Default: show common recipes
default:
	@echo "Usage: just <recipe>"
	@echo "  bootstrap             mise install (Python, uv, just per mise.toml)"
	@echo "  sync                  uv sync --project python --extra dev"
	@echo "  sync-all-extras       uv sync --project python --all-extras"
	@echo "  venv-path             print python/.venv path (after sync)"
	@echo "  python-path           print venv python interpreter path"
	@echo "  validate-gptoss-gsm8k  containerized GPT-OSS GSM8k benchmark"

# Install toolchain versions from mise.toml
bootstrap:
	mise install

# Editable dev environment (test deps via optional `dev` -> sglang[test])
sync:
	uv sync --project python --extra dev

# Full optional dependency groups (diffusion, ray, tracing, test, etc.)
sync-all-extras:
	uv sync --project python --all-extras

# After `just sync`, point your IDE at this virtualenv
venv-path:
	@echo "{{ justfile_directory() }}/python/.venv"

python-path:
	@echo "{{ justfile_directory() }}/python/.venv/bin/python"

# Run the containerized GPT-OSS-120B GSM8k validation benchmark
# using docker compose and local GPUs. This wraps
# scripts/run_container_gptoss_gsm8k_benchmark.sh.

validate-gptoss-gsm8k:
	@scripts/run_container_gptoss_gsm8k_benchmark.sh
