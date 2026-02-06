# Ferric Migration Utilities

This folder contains migration tooling for the Ferric Rust-infra migration plan.

## Dual-run parity harness

`ferric_parity_harness.py` replays a JSONL trace against:
- baseline runtime URL (current system)
- candidate runtime URL (new implementation)

and writes a structured JSON report with normalized comparisons.

### Usage

```bash
python scripts/migration/ferric_parity_harness.py \
  --trace-jsonl scripts/migration/ferric_sample_trace.jsonl \
  --baseline-url http://127.0.0.1:30000 \
  --candidate-url http://127.0.0.1:31000 \
  --report-json ferric_parity_report.json
```

### Local smoke test (no model server required)

```bash
python scripts/migration/mock_openai_server.py --port 39000 --variant baseline &
python scripts/migration/mock_openai_server.py --port 39001 --variant candidate_same &

python scripts/migration/ferric_parity_harness.py \
  --trace-jsonl scripts/migration/ferric_sample_trace.jsonl \
  --baseline-url http://127.0.0.1:39000 \
  --candidate-url http://127.0.0.1:39001 \
  --report-json ferric_parity_report.json

pkill -f \"scripts/migration/mock_openai_server.py --port 39000\" || true
pkill -f \"scripts/migration/mock_openai_server.py --port 39001\" || true
```

### Verdicts

- `match`: normalized outputs match
- `schema_mismatch`: both succeeded but normalized payload kinds differ
- `semantic_mismatch`: both succeeded but normalized outputs differ
- `timeout_mismatch`: timeout-like failure patterns differ between endpoints
- `transport_or_status_mismatch`: one side failed or status class differs
- `both_failed_same_status`: both failed with same status
- `both_failed_different_status`: both failed with different statuses

### Trace schema (JSONL)

Each line is one request object:

```json
{
  "id": "req-1",
  "endpoint": "/v1/chat/completions",
  "method": "POST",
  "headers": {"Content-Type": "application/json"},
  "body": {"model": "...", "messages": [{"role":"user","content":"..."}]},
  "timeout_s": 60
}
```

## Building traces from existing request dumps

Convert existing SGLang request dump pickles (e.g. crash/request dumps) to JSONL:

```bash
python scripts/migration/build_ferric_trace_from_dump.py \
  --input-file /path/to/crash_dump.pkl \
  --endpoint /generate \
  --output-jsonl scripts/migration/trace_from_dump.jsonl
```

Or from a folder:

```bash
python scripts/migration/build_ferric_trace_from_dump.py \
  --input-folder /path/to/request_dump_folder \
  --file-number 20 \
  --sort-by-start-time \
  --output-jsonl scripts/migration/trace_from_dump.jsonl
```
