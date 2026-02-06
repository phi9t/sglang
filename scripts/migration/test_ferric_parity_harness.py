#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("ferric_parity_harness.py")
SPEC = importlib.util.spec_from_file_location("ferric_parity_harness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FerricParityHarnessTests(unittest.TestCase):
    def _stream(self, *events: str):
        return iter(events)

    def test_streaming_text_normalization_matches_same_semantics(self):
        baseline = MODULE._extract_chat_stream(
            self._stream(
                'data: {"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
                'data: {"choices":[{"index":0,"delta":{"content":"OK: "},"finish_reason":null}]}',
                'data: {"choices":[{"index":0,"delta":{"content":"hello"},"finish_reason":null}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}',
                'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
                "data: [DONE]",
            )
        )
        candidate = MODULE._extract_chat_stream(
            self._stream(
                'data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"OK: hello"},"finish_reason":null}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}',
                'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
                "data: [DONE]",
            )
        )

        self.assertEqual(baseline, candidate)

    def test_streaming_tool_call_normalization_catches_differences(self):
        baseline = MODULE._extract_chat_stream(
            self._stream(
                'data: {"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
                'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"lookup_weather","arguments":"{\\"city\\":\\"" }}]},"finish_reason":null}]}',
                'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"San Francisco\\",\\"unit\\":\\"C\\"}"}}]},"finish_reason":null}],"usage":{"prompt_tokens":4,"completion_tokens":2,"total_tokens":6}}',
                'data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}',
                "data: [DONE]",
            )
        )
        candidate = MODULE._extract_chat_stream(
            self._stream(
                'data: {"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
                'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"lookup_forecast","arguments":"{\\"city\\":\\"" }}]},"finish_reason":null}]}',
                'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"San Francisco\\",\\"unit\\":\\"F\\"}"}}]},"finish_reason":null}],"usage":{"prompt_tokens":4,"completion_tokens":2,"total_tokens":6}}',
                'data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}',
                "data: [DONE]",
            )
        )

        self.assertNotEqual(baseline, candidate)
        self.assertEqual(
            baseline["tool_calls"][0][0]["function_name"],
            "lookup_weather",
        )
        self.assertEqual(
            candidate["tool_calls"][0][0]["function_name"],
            "lookup_forecast",
        )


if __name__ == "__main__":
    unittest.main()
