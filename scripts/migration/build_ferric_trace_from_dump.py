#!/usr/bin/env python3
"""
Build Ferric parity harness traces from SGLang request dump pickle files.

Input formats supported (best effort):
- list of tuples: (req, output, start_time, end_time)
- dict with key "requests" containing above tuple list

Output: JSONL for ferric_parity_harness.py.
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import pickle
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _normalize_mm_data_item(item: Any) -> Any:
    if isinstance(item, dict) and "url" in item:
        return item["url"]
    return item


def _normalize_mm_data(data: Any) -> Any:
    if data is None:
        return None
    if isinstance(data, list):
        out = []
        for sub in data:
            if isinstance(sub, list):
                out.append([_normalize_mm_data_item(x) for x in sub])
            else:
                out.append(_normalize_mm_data_item(sub))
        return out
    return _normalize_mm_data_item(data)


def _normalize_request_body(payload: Dict[str, Any]) -> Dict[str, Any]:
    for field in ("image_data", "video_data", "audio_data"):
        if field in payload:
            payload[field] = _normalize_mm_data(payload[field])
    return payload


def _obj_to_dict(obj: Any) -> Dict[str, Any]:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    raise TypeError(f"Unsupported request object type: {type(obj)!r}")


def _load_records(files: Iterable[Path]) -> List[Tuple[Any, Any, Any, Any]]:
    out: List[Tuple[Any, Any, Any, Any]] = []
    for path in files:
        with path.open("rb") as f:
            data = pickle.load(f)
        if isinstance(data, dict) and "requests" in data:
            records = data["requests"]
        else:
            records = data
        for rec in records:
            if isinstance(rec, tuple) and len(rec) >= 4:
                out.append((rec[0], rec[1], rec[2], rec[3]))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Ferric JSONL traces from dump pickle files"
    )
    parser.add_argument("--input-folder", type=str, default=None)
    parser.add_argument("--input-file", type=str, default=None)
    parser.add_argument("--file-number", type=int, default=1)
    parser.add_argument("--req-start", type=int, default=0)
    parser.add_argument("--req-number", type=int, default=1000)
    parser.add_argument(
        "--endpoint",
        type=str,
        default="/generate",
        help="Endpoint to replay against (default: /generate)",
    )
    parser.add_argument(
        "--output-jsonl",
        type=str,
        required=True,
        help="Output JSONL path for parity harness",
    )
    parser.add_argument("--sort-by-start-time", action="store_true")
    parser.add_argument("--timeout-s", type=int, default=60)
    args = parser.parse_args()

    files: List[Path] = []
    if args.input_file:
        files = [Path(args.input_file)]
    elif args.input_folder:
        globbed = sorted(glob.glob(str(Path(args.input_folder) / "*.pkl")))
        files = [Path(x) for x in globbed[: args.file_number]]
    else:
        raise SystemExit("Provide --input-file or --input-folder")

    records = _load_records(files)
    if args.sort_by_start_time:
        records.sort(key=lambda x: x[2])

    sliced = records[args.req_start : args.req_start + args.req_number]

    out_path = Path(args.output_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i, (req, _output, _start_time, _end_time) in enumerate(sliced):
            try:
                body = _obj_to_dict(req)
                body = _normalize_request_body(body)
            except Exception:
                skipped += 1
                continue

            rec = {
                "id": f"dump-{i}",
                "endpoint": args.endpoint,
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": body,
                "timeout_s": args.timeout_s,
            }
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")
            written += 1

    print(
        json.dumps(
            {
                "input_files": [str(p) for p in files],
                "records_seen": len(sliced),
                "written": written,
                "skipped": skipped,
                "output_jsonl": str(out_path),
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
