# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SGLang is a high-performance serving framework for large language models (LLMs) and multimodal models. It provides fast inference with RadixAttention prefix caching, zero-overhead CPU scheduler, continuous batching, and support for NVIDIA/AMD GPUs, Intel CPUs, Google TPUs, and Ascend NPUs.

## Repository Structure

```
python/sglang/          # Main Python package
  lang/                 # Frontend language API (gen, function, select, etc.)
  srt/                  # SGLang Runtime backend engine
    server_args.py      # Server configuration (~5600 lines)
    models/             # Model-specific implementations
    model_executor/     # Model execution layer
    sampling/           # Token sampling
    entrypoints/        # HTTP/gRPC servers
  multimodal_gen/       # Diffusion model generation framework
  jit_kernel/           # JIT-compiled kernels
sgl-kernel/             # Optimized CUDA/C++ kernels
sgl-model-gateway/      # Rust-based model routing gateway
test/                   # Test infrastructure
  srt/                  # Backend runtime tests
  lang/                 # Frontend language tests
  registered/           # Registry-based CI tests
docs/                   # Sphinx documentation (Jupyter notebooks + Markdown)
benchmark/              # Benchmarking scripts
```

## Development Commands

### Installation
```bash
cd python
pip install -e .                    # Editable install
pip install -e ".[dev]"             # With dev dependencies
pip install -e ".[diffusion]"       # With diffusion support
```

### Running Tests
```bash
# Single test file
cd test/srt
python3 test_srt_endpoint.py

# Single test case
python3 test_srt_endpoint.py TestSRTEndpoint.test_simple_decode

# Test suite
python3 run_suite.py --suite per-commit

# Registry-based tests
python test/run_suite.py --hw cuda --suite stage-b-test-small-1-gpu
```

### Code Quality
```bash
pre-commit run --all-files          # Format and lint (required before PR)
```

Pre-commit runs: black (formatting), isort (imports), ruff (F401/F821 checks), clang-format (C++/CUDA), codespell, nbstripout.

### Launching Server
```bash
python3 -m sglang.launch_server --model meta-llama/Llama-3.1-8B-Instruct
```

### Building Kernels (sgl-kernel/)
```bash
make build
make build MAX_JOBS=2 CMAKE_ARGS="-DSGL_KERNEL_COMPILE_THREADS=1"  # Limited resources
```

### Building Gateway (sgl-model-gateway/)
```bash
cargo build --release                           # Rust binary
cd bindings/python && maturin develop           # Python bindings
```

### Documentation (docs/)
```bash
make html                           # Build HTML docs
make serve                          # Serve with auto-rebuild
```

## Architecture Overview

**Frontend (lang/)**: Public API (`gen()`, `function()`, `select()`), intermediate representation, interpreter, and backends (RuntimeEndpoint, OpenAI, Anthropic).

**Backend Runtime (srt/)**: Model executor runs forward passes, sampling selects tokens, memory cache manages KV cache with RadixAttention, scheduler batches requests with continuous batching.

**Request Flow**: Client → HTTP/gRPC endpoint → (optional gateway routing) → scheduler batches requests → model executor → optimized kernels → response streamed back.

## Testing Infrastructure

Tests use unittest framework. The CI registry system in `test/registered/` uses decorators for configuration:

```python
from sglang.test.ci.ci_register import register_cuda_ci

register_cuda_ci(est_time=80, suite="stage-b-test-small-1-gpu")  # 5090 runner
register_cuda_ci(est_time=120, suite="stage-b-test-large-1-gpu") # H100 runner (>32GB or SM90 required)
```

**Suites**: Per-commit uses stage-a/b/c-test-* suites. Nightly uses nightly-*-gpu suites.

When adding tests:
- Prefer `stage-b-test-small-1-gpu` (5090) for 1-GPU tests
- Use `stage-b-test-large-1-gpu` (H100) for large models, FP8/MXFP4, or FA3 backend
- Add `unittest.main()` or `sys.exit(pytest.main([__file__]))` to test files
- Reuse servers across test cases to reduce launch time

## Key Dependencies

- torch==2.9.1, transformers==4.57.1
- flashinfer_python==0.6.2, sgl-kernel==0.3.21
- grpcio==1.75.1, xgrammar==0.1.27, outlines==0.1.11

## PR Process

1. Fill out PR checklist template
2. Get `run-ci` label to trigger CI
3. Merge Oncall coordinates review; Codeowners must approve protected files
4. CI must pass (or Merge Oncall can bypass for important PRs)

Slack channels: #dev, #pull-request, #ci-cd-build-release at slack.sglang.io
