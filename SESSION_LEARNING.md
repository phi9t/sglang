# Session learning checklist

Track mastery of this session's work on SGLang local tooling + GPT-OSS Docker workflow.

## Stage 1 — Problem & session arc
- [ ] What uncommitted work existed at the start (staged vs unstaged)?
- [ ] Why run GPT-OSS / GSM8k **only inside Docker** (not host Python)?
- [ ] What the B200 machine implies for defaults (GPUs, model size, TP)?
- [ ] Why we split commits (benchmark vs compose vs uv)?

## Stage 2 — GPT-OSS Docker solution
- [ ] What each artifact does: `Justfile`, `compose.gptoss_gsm8k.yaml`, benchmark script, `foundation.org`
- [ ] Healthcheck / curl / `--tool-server demo` risks
- [ ] E2E smoke test design (`xeno/run_gptoss_e2e.sh` + `docker/compose.xeno.yaml`)
- [ ] Why compose files live under `docker/` (include pattern, no duplication)

## Stage 3 — Developer toolchain (mise + just + uv)
- [ ] Role split: mise pins CLIs, uv installs Python deps, just is the entry surface
- [ ] Why `--project python` (pyproject lives under `python/`)
- [ ] Why `python/uv.lock` exists and when to regenerate it
- [ ] `[tool.uv] exclude-dependencies` vs old `exclude` field

## Stage 4 — Environment variables (single source of truth)
- [ ] Three layers: runtime (`environ.py`), Compose interpolation, script pass-through
- [ ] What `docker/ENVIRONMENT.md` indexes vs what stays in code
- [ ] HF cache vs SGLang cache mount split in `compose.yaml`

## Stage 5 — Broader impact
- [ ] Who is affected: lab B200 users vs upstream contributors vs CI
- [ ] What is **not** in the committed branch yet (unstaged compose/uv changes)
- [ ] Safe next steps (run e2e, second commit, devcontainer parity)

---

## Progress log
| Stage | Status | Notes |
|-------|--------|-------|
| 1 | **In progress** | |
| 2 | pending | |
| 3 | pending | |
| 4 | pending | |
| 5 | pending | |
