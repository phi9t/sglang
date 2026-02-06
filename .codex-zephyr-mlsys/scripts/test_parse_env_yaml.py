#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("parse-env-yaml.py")


class ParseEnvYamlTests(unittest.TestCase):
    def _write_yaml(self) -> Path:
        yaml_text = textwrap.dedent(
            """
            apiVersion: zephyr-mlsys/v1
            metadata:
              name: literal-test
              description: 'quote " dollar $(echo injected) backtick `uname`'
            spec:
              venvs:
                - name: main
                  packages: ["pkg-a", "pkg-b"]
                  overrides: ["constraints.txt"]
            """
        )
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(yaml_text)
            return Path(tmp.name)

    def test_json_output_preserves_literal_shell_metacharacters(self):
        yaml_path = self._write_yaml()

        try:
            result = subprocess.run(
                ["python3", str(SCRIPT), "--output", "json", str(yaml_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            yaml_path.unlink(missing_ok=True)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["name"], "literal-test")
        self.assertEqual(
            payload["description"],
            'quote " dollar $(echo injected) backtick `uname`',
        )
        self.assertEqual(payload["venvs"][0]["packages"], ["pkg-a", "pkg-b"])

    def test_shell_output_is_safe_to_source(self):
        yaml_path = self._write_yaml()

        try:
            result = subprocess.run(
                [
                    "bash",
                    "-lc",
                    f'eval "$(python3 {SCRIPT} {yaml_path})"; printf "%s" "$ENV_DESCRIPTION"',
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            yaml_path.unlink(missing_ok=True)

        self.assertEqual(
            result.stdout,
            'quote " dollar $(echo injected) backtick `uname`',
        )


if __name__ == "__main__":
    unittest.main()
