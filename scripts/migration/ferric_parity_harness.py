#!/usr/bin/env python3
"""
Dual-run parity harness for Ferric migration.

This tool replays request traces against two runtime endpoints:
- baseline (current Python runtime)
- candidate (new Rust-infra runtime path)

It emits a machine-readable JSON report with normalized comparisons.

Trace format (JSONL):
{
  "id": "req-1",
  "endpoint": "/v1/chat/completions",
  "method": "POST",
  "headers": {"Content-Type": "application/json"},
  "body": { ... OpenAI-compatible payload ... },
  "timeout_s": 60
}

Notes:
- Streaming mode is inferred from request body field "stream".
- For streaming chat/completions, this script assembles text from SSE chunks.
- Volatile fields are ignored in normalization (id, created, etc.).
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
from urllib import error as urlerror
from urllib import request as urlrequest

DEFAULT_TIMEOUT_S = 60
DEFAULT_MAX_WORKERS = 8
VOLATILE_TOP_LEVEL_FIELDS = {
    "id",
    "created",
    "system_fingerprint",
    "request_id",
}


@dataclass
class TraceItem:
    trace_index: int
    req_id: str
    endpoint: str
    method: str
    headers: Dict[str, str]
    body: Dict[str, Any]
    timeout_s: int


@dataclass
class EndpointResult:
    ok: bool
    status_code: Optional[int]
    latency_ms: int
    error: Optional[str]
    normalized: Dict[str, Any]


def _normalize_json_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in VOLATILE_TOP_LEVEL_FIELDS:
                continue
            out[k] = _normalize_json_obj(v)
        return out
    if isinstance(obj, list):
        return [_normalize_json_obj(x) for x in obj]
    return obj


def _extract_chat_non_stream(payload: Dict[str, Any]) -> Dict[str, Any]:
    choices = payload.get("choices", [])
    texts: List[str] = []
    finish_reasons: List[Any] = []
    for c in choices:
        msg = c.get("message", {})
        content = msg.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            # Multimodal content blocks; keep stable JSON encoding.
            texts.append(json.dumps(content, sort_keys=True, ensure_ascii=True))
        else:
            texts.append("")
        finish_reasons.append(c.get("finish_reason"))

    usage = payload.get("usage", {})
    return {
        "kind": "chat_non_stream",
        "texts": texts,
        "finish_reasons": finish_reasons,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "raw": _normalize_json_obj(payload),
    }


def _extract_chat_stream(lines: Iterator[str]) -> Dict[str, Any]:
    texts_by_index: Dict[int, List[str]] = {}
    content_blocks_by_index: Dict[int, List[Any]] = {}
    roles_by_index: Dict[int, str] = {}
    refusals_by_index: Dict[int, List[str]] = {}
    refusal_blocks_by_index: Dict[int, List[Any]] = {}
    tool_calls_by_index: Dict[int, Dict[int, Dict[str, Any]]] = {}
    finish_reasons: Dict[int, Any] = {}
    usage: Dict[str, Any] = {}
    saw_done = False

    for line in lines:
        if not line:
            continue
        if not line.startswith("data:"):
            continue

        data = line[len("data:") :].strip()
        if data == "[DONE]":
            saw_done = True
            break

        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue

        for c in chunk.get("choices", []):
            idx = c.get("index", 0)
            delta = c.get("delta", {})
            role = delta.get("role")
            if isinstance(role, str):
                roles_by_index[idx] = role

            piece = delta.get("content")
            if isinstance(piece, str):
                texts_by_index.setdefault(idx, []).append(piece)
            elif isinstance(piece, list):
                content_blocks_by_index.setdefault(idx, []).extend(
                    _normalize_json_obj(piece)
                )

            refusal = delta.get("refusal")
            if isinstance(refusal, str):
                refusals_by_index.setdefault(idx, []).append(refusal)
            elif isinstance(refusal, list):
                refusal_blocks_by_index.setdefault(idx, []).extend(
                    _normalize_json_obj(refusal)
                )

            for tool_call in delta.get("tool_calls", []) or []:
                tool_index = int(tool_call.get("index", 0))
                normalized_tool = tool_calls_by_index.setdefault(idx, {}).setdefault(
                    tool_index,
                    {
                        "id": None,
                        "type": None,
                        "function_name": None,
                        "arguments_parts": [],
                    },
                )
                if tool_call.get("id") is not None:
                    normalized_tool["id"] = tool_call["id"]
                if tool_call.get("type") is not None:
                    normalized_tool["type"] = tool_call["type"]

                function = tool_call.get("function") or {}
                if function.get("name") is not None:
                    normalized_tool["function_name"] = function["name"]
                arguments = function.get("arguments")
                if isinstance(arguments, str):
                    normalized_tool["arguments_parts"].append(arguments)

            if c.get("finish_reason") is not None:
                finish_reasons[idx] = c.get("finish_reason")

        if "usage" in chunk and isinstance(chunk["usage"], dict):
            usage = chunk["usage"]

    choice_indexes = sorted(
        set(texts_by_index)
        | set(content_blocks_by_index)
        | set(roles_by_index)
        | set(refusals_by_index)
        | set(refusal_blocks_by_index)
        | set(tool_calls_by_index)
        | set(finish_reasons)
    )
    final_texts = ["".join(texts_by_index.get(idx, [])) for idx in choice_indexes]
    final_finish = [finish_reasons.get(idx) for idx in choice_indexes]
    final_roles = [roles_by_index.get(idx) for idx in choice_indexes]
    final_refusals = ["".join(refusals_by_index.get(idx, [])) for idx in choice_indexes]
    final_tool_calls = []
    for idx in choice_indexes:
        tool_calls = []
        for tool_index in sorted(tool_calls_by_index.get(idx, {})):
            tool = tool_calls_by_index[idx][tool_index]
            tool_calls.append(
                {
                    "id": tool["id"],
                    "type": tool["type"],
                    "function_name": tool["function_name"],
                    "arguments": "".join(tool["arguments_parts"]),
                }
            )
        final_tool_calls.append(tool_calls)

    return {
        "kind": "chat_stream",
        "texts": final_texts,
        "roles": final_roles,
        "content_blocks": [content_blocks_by_index.get(idx, []) for idx in choice_indexes],
        "refusals": final_refusals,
        "refusal_blocks": [
            refusal_blocks_by_index.get(idx, []) for idx in choice_indexes
        ],
        "tool_calls": final_tool_calls,
        "finish_reasons": final_finish,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "saw_done": saw_done,
    }


def _extract_embedding(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data", [])
    dims = []
    for item in data:
        emb = item.get("embedding")
        if isinstance(emb, list):
            dims.append(len(emb))
        else:
            dims.append(None)

    usage = payload.get("usage", {})
    return {
        "kind": "embedding",
        "embedding_dims": dims,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "raw": _normalize_json_obj(payload),
    }


def _normalize_result(endpoint: str, stream: bool, payload: Any) -> Dict[str, Any]:
    if endpoint == "/v1/chat/completions":
        if stream:
            return _extract_chat_stream(payload)
        return _extract_chat_non_stream(payload)

    if endpoint == "/v1/embeddings":
        return _extract_embedding(payload)

    # Generic fallback for other endpoints.
    return {
        "kind": "generic",
        "raw": _normalize_json_obj(payload),
    }


def _read_sse_lines(resp) -> Iterator[str]:
    for raw in resp:
        yield raw.decode("utf-8", errors="replace").rstrip("\n")


def _request_one(base_url: str, item: TraceItem) -> EndpointResult:
    url = base_url.rstrip("/") + item.endpoint
    stream = bool(item.body.get("stream", False))
    start = time.monotonic()
    req_bytes = json.dumps(item.body, ensure_ascii=True).encode("utf-8")
    headers = dict(item.headers)
    headers.setdefault("Content-Type", "application/json")
    req = urlrequest.Request(
        url=url,
        data=req_bytes,
        headers=headers,
        method=item.method,
    )

    try:
        with urlrequest.urlopen(req, timeout=item.timeout_s) as resp:
            latency_ms = int((time.monotonic() - start) * 1000)
            status_code = int(resp.getcode())

            if stream and item.endpoint == "/v1/chat/completions":
                payload = _read_sse_lines(resp)
            else:
                raw_text = resp.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw_text)
                except Exception:
                    payload = {"raw_text": raw_text}

            normalized = _normalize_result(item.endpoint, stream, payload)
            return EndpointResult(
                ok=True,
                status_code=status_code,
                latency_ms=latency_ms,
                error=None,
                normalized=normalized,
            )
    except urlerror.HTTPError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = str(e)
        return EndpointResult(
            ok=False,
            status_code=int(e.code),
            latency_ms=latency_ms,
            error=err_body,
            normalized={},
        )
    except Exception as e:  # pragma: no cover - best-effort runtime tool
        latency_ms = int((time.monotonic() - start) * 1000)
        return EndpointResult(
            ok=False,
            status_code=None,
            latency_ms=latency_ms,
            error=f"{type(e).__name__}: {e}",
            normalized={},
        )


def _compare_results(baseline: EndpointResult, candidate: EndpointResult) -> Tuple[str, Dict[str, Any]]:
    if baseline.ok and candidate.ok and baseline.normalized != candidate.normalized:
        if baseline.normalized.get("kind") != candidate.normalized.get("kind"):
            return "schema_mismatch", {
                "baseline_kind": baseline.normalized.get("kind"),
                "candidate_kind": candidate.normalized.get("kind"),
            }

    if baseline.ok != candidate.ok:
        b_err = (baseline.error or "").lower()
        c_err = (candidate.error or "").lower()
        timeout_markers = ("timeout", "timed out")
        if any(m in b_err for m in timeout_markers) or any(
            m in c_err for m in timeout_markers
        ):
            return "timeout_mismatch", {
                "baseline_ok": baseline.ok,
                "candidate_ok": candidate.ok,
            }
        return "transport_or_status_mismatch", {
            "baseline_ok": baseline.ok,
            "candidate_ok": candidate.ok,
            "baseline_status": baseline.status_code,
            "candidate_status": candidate.status_code,
        }

    if not baseline.ok and not candidate.ok:
        # Both failed; compare status and error string shape.
        if baseline.status_code == candidate.status_code:
            return "both_failed_same_status", {}
        return "both_failed_different_status", {
            "baseline_status": baseline.status_code,
            "candidate_status": candidate.status_code,
        }

    if baseline.normalized == candidate.normalized:
        return "match", {}

    return "semantic_mismatch", {
        "baseline_kind": baseline.normalized.get("kind"),
        "candidate_kind": candidate.normalized.get("kind"),
    }


def _load_trace_items(path: Path, default_timeout_s: int) -> List[TraceItem]:
    items: List[TraceItem] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)

            req_id = rec.get("id") or f"line-{lineno}"
            endpoint = rec.get("endpoint", "/v1/chat/completions")
            method = str(rec.get("method", "POST")).upper()
            headers = rec.get("headers") or {"Content-Type": "application/json"}
            body = rec.get("body") or {}
            timeout_s = int(rec.get("timeout_s", default_timeout_s))

            items.append(
                TraceItem(
                    trace_index=len(items),
                    req_id=req_id,
                    endpoint=endpoint,
                    method=method,
                    headers=headers,
                    body=body,
                    timeout_s=timeout_s,
                )
            )
    return items


def _run_case(item: TraceItem, baseline_url: str, candidate_url: str) -> Dict[str, Any]:
    base = _request_one(baseline_url, item)
    cand = _request_one(candidate_url, item)
    verdict, detail = _compare_results(base, cand)

    return {
        "trace_index": item.trace_index,
        "id": item.req_id,
        "endpoint": item.endpoint,
        "verdict": verdict,
        "verdict_detail": detail,
        "baseline": {
            "ok": base.ok,
            "status_code": base.status_code,
            "latency_ms": base.latency_ms,
            "error": base.error,
            "normalized": base.normalized,
        },
        "candidate": {
            "ok": cand.ok,
            "status_code": cand.status_code,
            "latency_ms": cand.latency_ms,
            "error": cand.error,
            "normalized": cand.normalized,
        },
    }


def _summarize(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    by_verdict: Dict[str, int] = {}
    baseline_latencies: List[int] = []
    candidate_latencies: List[int] = []

    for r in results:
        total += 1
        v = r["verdict"]
        by_verdict[v] = by_verdict.get(v, 0) + 1

        b_lat = r["baseline"]["latency_ms"]
        c_lat = r["candidate"]["latency_ms"]
        if isinstance(b_lat, int):
            baseline_latencies.append(b_lat)
        if isinstance(c_lat, int):
            candidate_latencies.append(c_lat)

    def _p50(vals: List[int]) -> Optional[int]:
        if not vals:
            return None
        vals = sorted(vals)
        return vals[len(vals) // 2]

    return {
        "total": total,
        "by_verdict": by_verdict,
        "match_rate": (by_verdict.get("match", 0) / total) if total else 0.0,
        "baseline_latency_ms_p50": _p50(baseline_latencies),
        "candidate_latency_ms_p50": _p50(candidate_latencies),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ferric dual-run parity harness")
    parser.add_argument("--trace-jsonl", required=True, help="Path to JSONL trace file")
    parser.add_argument("--baseline-url", required=True, help="Baseline endpoint base URL")
    parser.add_argument("--candidate-url", required=True, help="Candidate endpoint base URL")
    parser.add_argument(
        "--report-json",
        default="ferric_parity_report.json",
        help="Output report file path",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Max parallel workers",
    )
    parser.add_argument(
        "--timeout-s",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help="Default request timeout (seconds)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after first mismatch/error verdict",
    )

    args = parser.parse_args()

    trace_path = Path(args.trace_jsonl)
    report_path = Path(args.report_json)
    items = _load_trace_items(trace_path, args.timeout_s)

    results: List[Dict[str, Any]] = []

    if args.max_workers <= 1:
        for item in items:
            out = _run_case(item, args.baseline_url, args.candidate_url)
            results.append(out)
            if args.fail_fast and out["verdict"] != "match":
                break
    else:
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            fut_map = {
                pool.submit(_run_case, item, args.baseline_url, args.candidate_url): item
                for item in items
            }
            for fut in as_completed(fut_map):
                out = fut.result()
                results.append(out)
                if args.fail_fast and out["verdict"] != "match":
                    break

    # keep deterministic ordering by input trace order
    results.sort(key=lambda x: int(x["trace_index"]))

    report = {
        "metadata": {
            "trace_jsonl": str(trace_path),
            "baseline_url": args.baseline_url,
            "candidate_url": args.candidate_url,
            "generated_at_epoch_s": int(time.time()),
        },
        "summary": _summarize(results),
        "results": results,
    }

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2, ensure_ascii=True))
    print(f"Wrote report: {report_path}")


if __name__ == "__main__":
    main()
