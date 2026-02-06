#!/usr/bin/env python3
"""
Minimal mock OpenAI-compatible server for migration parity harness smoke tests.

Endpoints:
- POST /v1/chat/completions (streaming + non-streaming)
- POST /v1/embeddings
- GET  /health

Variants:
- baseline: deterministic canonical responses
- candidate_same: identical to baseline
- candidate_diff: intentionally different assistant content for mismatch testing
- candidate_tool_diff: intentionally different streamed tool call for mismatch testing
"""

from __future__ import annotations

import argparse
import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List


class MockHandler(BaseHTTPRequestHandler):
    server_version = "OptionBMockOpenAI/0.1"

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _build_chat_text(self, payload: Dict[str, Any]) -> str:
        # Deterministic mock text to keep parity stable.
        user_msgs: List[str] = []
        for m in payload.get("messages", []):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                user_msgs.append(m["content"])

        prompt = " ".join(user_msgs).strip()
        if not prompt:
            prompt = "(empty)"

        variant = self.server.variant
        if variant == "candidate_diff":
            return f"DIFF: {prompt}"
        return f"OK: {prompt}"

    def _chat_non_stream(self, payload: Dict[str, Any]) -> None:
        text = self._build_chat_text(payload)
        resp = {
            "id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model", "mock-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 4,
                "completion_tokens": 4,
                "total_tokens": 8,
            },
        }
        self._send_json(resp)

    def _chat_stream(self, payload: Dict[str, Any]) -> None:
        if payload.get("tools"):
            self._chat_stream_tool_call(payload)
            return

        text = self._build_chat_text(payload)
        pieces = text.split(" ")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        for piece in pieces:
            chunk = {
                "id": f"chatcmpl-{int(time.time() * 1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": payload.get("model", "mock-model"),
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": piece + " "},
                        "finish_reason": None,
                    }
                ],
            }
            line = f"data: {json.dumps(chunk, ensure_ascii=True)}\n\n"
            self.wfile.write(line.encode("utf-8"))
            self.wfile.flush()

        final_chunk = {
            "id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": payload.get("model", "mock-model"),
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 4,
                "completion_tokens": len(pieces),
                "total_tokens": 4 + len(pieces),
            },
        }
        self.wfile.write(
            f"data: {json.dumps(final_chunk, ensure_ascii=True)}\n\n".encode("utf-8")
        )
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _chat_stream_tool_call(self, payload: Dict[str, Any]) -> None:
        variant = self.server.variant
        tool_name = "lookup_weather"
        tool_args = '{"city":"San Francisco","unit":"C"}'
        if variant == "candidate_tool_diff":
            tool_name = "lookup_forecast"
            tool_args = '{"city":"San Francisco","unit":"F"}'

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        chunks = [
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant"},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": tool_name, "arguments": '{"city":"'},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": tool_args[len('{"city":"') :]},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 2,
                    "total_tokens": 6,
                },
            },
        ]
        for chunk in chunks:
            chunk.update(
                {
                    "id": f"chatcmpl-{int(time.time() * 1000)}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": payload.get("model", "mock-model"),
                }
            )
            self.wfile.write(
                f"data: {json.dumps(chunk, ensure_ascii=True)}\n\n".encode("utf-8")
            )
            self.wfile.flush()

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _embeddings(self, payload: Dict[str, Any]) -> None:
        inp = payload.get("input")
        if isinstance(inp, list):
            n = len(inp)
        else:
            n = 1
        data = []
        for i in range(n):
            data.append({"object": "embedding", "index": i, "embedding": [0.1, 0.2, 0.3]})

        resp = {
            "object": "list",
            "data": data,
            "model": payload.get("model", "mock-embedding-model"),
            "usage": {"prompt_tokens": 3, "total_tokens": 3},
        }
        self._send_json(resp)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._send_json({"ok": True, "variant": self.server.variant})
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self):  # noqa: N802
        payload = self._read_json()

        if self.path == "/v1/chat/completions":
            if bool(payload.get("stream", False)):
                self._chat_stream(payload)
            else:
                self._chat_non_stream(payload)
            return

        if self.path == "/v1/embeddings":
            self._embeddings(payload)
            return

        self._send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Quiet by default to keep harness logs readable.
        if self.server.verbose:
            super().log_message(format, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock OpenAI-compatible server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--variant",
        choices=[
            "baseline",
            "candidate_same",
            "candidate_diff",
            "candidate_tool_diff",
        ],
        default="baseline",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockHandler)
    server.variant = args.variant
    server.verbose = args.verbose

    print(
        f"mock_openai_server listening on http://{args.host}:{args.port} variant={args.variant}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
