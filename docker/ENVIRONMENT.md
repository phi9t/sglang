# Environment variables (single index)

Use this file as the **one place to learn where variables are defined**, across Docker, scripts, and Python.

**Maintainers:** keep this file as the index. When adding Compose interpolation vars or new `SGLANG_*` runtime flags, update the table below or `python/sglang/srt/environ.py` respectively—avoid duplicating long lists only in script comments. Optional one-line pointers elsewhere:

- Top of `docker/compose.yaml` / `docker/compose.gptoss_gsm8k.yaml`: `# Host-side env: see ENVIRONMENT.md`
- Module docstring at top of `python/sglang/srt/environ.py`: point here for Docker vs in-process split
- `scripts/run_container_gptoss_gsm8k_benchmark.sh` / `xeno/run_gptoss_e2e.sh`: `# Env index: …/docker/ENVIRONMENT.md`

## 1. SGLang runtime (inside the server process)

**Source of truth:** [`python/sglang/srt/environ.py`](../python/sglang/srt/environ.py) — the `Envs` class lists supported `SGLANG_*` / related knobs read at runtime.

For diffusion/multimodal build and runtime env vars, see [`python/sglang/multimodal_gen/envs.py`](../python/sglang/multimodal_gen/envs.py).

## 2. Docker Compose (host interpolation)

These names are expanded **on the host** when you run `docker compose` (defaults shown as `${VAR:-default}`).

### [`compose.yaml`](compose.yaml) — general serving stack

| Variable | Role |
|----------|------|
| `IMAGE` | Container image (default `lmsysorg/sglang:latest`) |
| `SHM_SIZE` | Shared memory limit (default `64g`) |
| `HF_CACHE_DIR` | Host Hugging Face cache mounted at `/data/hf-cache` |
| `SGLANG_CACHE_ROOT` | Host SGLang/compiler caches mounted at `/data/sglang-cache` |
| `HF_TOKEN` | Optional Hugging Face token |
| `SGLANG_UID`, `SGLANG_GID` | Container user (pass host `id -u` / `id -g`) |
| `CUDA_VISIBLE_DEVICES` | GPU selection inside the container |
| `MODEL_PATH` | Model id or path for `launch_server` |
| `PORT` | Listen port (default `30000`; healthcheck uses the same) |
| `TP` | Tensor parallel size |
| `EXTRA_ARGS` | Extra CLI tokens appended to `launch_server` |

Fixed paths inside the container (`HF_HOME`, `SGLANG_CACHE_DIR`, `FLASHINFER_WORKSPACE_DIR`, etc.) are set in the YAML; adjust behavior by changing mounts and the variables above—not by editing those literals unless you intend to change layout.

### [`compose.gptoss_gsm8k.yaml`](compose.gptoss_gsm8k.yaml) — GPT-OSS GSM8k / Xeno include stack

| Variable | Role |
|----------|------|
| `IMAGE` | Container image |
| `CONTAINER_NAME` | Docker container name (default `sglang-gptoss-120b-test`) |
| `HOST_PORT` | Published host port for `30000` in the container |
| `HF_CACHE_DIR` | Host HF cache directory |
| `HF_TOKEN` | Optional Hugging Face token |
| `SGLANG_UID`, `SGLANG_GID` | Required for `user:` mapping |
| `MODEL_PATH` | Model id (default `openai/gpt-oss-120b`) |
| `TP` | Tensor parallel degree |

[`compose.xeno.yaml`](compose.xeno.yaml) only `include`s `compose.gptoss_gsm8k.yaml`; it does not add variables.

## 3. Shell helpers (pass-through to Compose)

Scripts export the same names as the Compose tables above; **do not duplicate long env lists in script headers** — refer here instead.

| Script | Purpose |
|--------|---------|
| [`scripts/run_container_gptoss_gsm8k_benchmark.sh`](../scripts/run_container_gptoss_gsm8k_benchmark.sh) | GPT-OSS GSM8k benchmark using `compose.gptoss_gsm8k.yaml` |
| [`xeno/run_gptoss_e2e.sh`](../xeno/run_gptoss_e2e.sh) | Smoke test using `docker/compose.xeno.yaml` (includes GPT-OSS stack) |

Optional overrides are documented in each script’s header (`GPTOSS_E2E_*`, etc.).

## 4. Python / uv local install

Project dependencies and optional `[tool.uv]` settings live in [`python/pyproject.toml`](../python/pyproject.toml). That is separate from runtime `SGLANG_*` env vars.
