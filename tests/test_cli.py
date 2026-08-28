import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).parents[1]
PYTHON = sys.executable


def run(*args):
    return subprocess.run([PYTHON, "-m", "brick_builder.cli", *map(str, args)], cwd=ROOT, text=True, capture_output=True)


class CliContractTests(unittest.TestCase):
    def assert_json(self, result, code=0):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stderr, "")
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        return json.loads(lines[0])

    def test_catalog_contract(self):
        data = self.assert_json(run("catalog"))
        part = next(p for p in data["parts"] if p["part"] == "3004.dat")
        self.assertEqual((part["x_studs"], part["z_studs"]), (2, 1))
        self.assertTrue(data["allowed_colours"])
        self.assertEqual(data["allowed_colours"], sorted(data["allowed_colours"], key=lambda c: c["code"]))
        self.assertTrue(all(set(("code", "name")) <= set(c) for c in data["allowed_colours"]))

    def test_validate_and_analyze_contract(self):
        model = ROOT / "examples/reference_models/rotated-one-stud.json"
        valid = self.assert_json(run("validate", model))
        self.assertTrue(valid["valid"])
        analysis = self.assert_json(run("analyze", model))
        self.assertEqual(analysis["edges"], [["base", "upper"]])
        self.assertEqual(analysis["root_id"], "base")

    def test_invalid_and_disconnected_models_are_structured(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text(json.dumps({"schema_version": 1, "model_id": "Bad ID", "name": "bad", "parts": []}))
            data = self.assert_json(run("validate", path), 2)
            self.assertFalse(data["valid"])
            self.assertTrue(all(set(("code", "path", "message", "repair_hint")) <= set(i) for i in data["issues"]))

            disconnected = {"schema_version": 1, "model_id": "disconnected", "name": "x", "parts": [
                {"id": "a", "part": "3005.dat", "colour": 4, "translation_ldu": [0, 0, 0], "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1]},
                {"id": "b", "part": "3005.dat", "colour": 1, "translation_ldu": [100, 0, 0], "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1]}]}
            path.write_text(json.dumps(disconnected))
            data = self.assert_json(run("validate", path), 2)
            self.assertTrue(any(i["code"] == "DISCONNECTED_ASSEMBLY" for i in data["issues"]))

    def test_invalid_analyze_and_compile_are_structured(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "invalid.json"
            path.write_text("{}")
            self.assertFalse(self.assert_json(run("analyze", path), 2)["valid"])
            output = Path(d) / "should-not-exist.ldr"
            self.assertFalse(self.assert_json(run("compile", path, output), 2)["valid"])
            self.assertFalse(output.exists())

    def test_internal_handler_error_is_exit_three(self):
        from brick_builder import cli
        with patch.object(cli, "_catalog", side_effect=RuntimeError("boom")):
            with patch("sys.stdout") as stdout:
                status = cli.main(["catalog"])
        self.assertEqual(status, 3)
        payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))
        self.assertEqual(payload["issues"][0]["code"], "INTERNAL_ERROR")

    def test_compile_hash_and_legacy_shim(self):
        model = ROOT / "examples/reference_models/rotated-one-stud.json"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "model.ldr"
            data = self.assert_json(run("compile", model, out))
            self.assertTrue(out.exists())
            self.assertEqual(data["sha256"], hashlib.sha256(out.read_bytes()).hexdigest())
            legacy = self.assert_json(run(model, Path(d) / "legacy.ldr"))
            self.assertTrue(legacy["valid"])
