"""
Usage:
1) Build and activate the MLSys sglang environment in Zephyr infra.
2) Launch server:
   python -m sglang.launch_server \
     --model Qwen/Qwen3.5-0.8B \
     --model-impl transformers \
     --host 0.0.0.0 \
     --port 30000
3) Run this script:
   python examples/runtime/qwen35_0_8b_chat_inference.py
"""

import argparse
import json
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a simple chat completion request to a local SGLang server."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:30000",
        help="SGLang server base URL",
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen3.5-0.8B",
        help="Model name sent in the OpenAI-compatible request",
    )
    parser.add_argument(
        "--prompt",
        default="In one short paragraph, explain what SGLang is.",
        help="User prompt",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=128,
        help="Maximum completion tokens",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url = f"{args.base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 1

    data = json.loads(raw)
    message = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    print("=== Assistant Response ===")
    print(message)
    print("\n=== Token Usage ===")
    print(json.dumps(usage, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
