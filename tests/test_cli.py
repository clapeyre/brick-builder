import re
import hashlib
import json
import subprocess
import sys
import tempfile
import pytest
from pathlib import Path

ROOT = Path(__file__).parents[1]
PYTHON = sys.executable


def run(*args):
    return subprocess.run([PYTHON, "-m", "brick_builder.cli", *map(str, args)], cwd=ROOT, text=True, capture_output=True)


class TestCliContract:
    def parse_json(self, result, code=0):
        assert result.returncode == code, result.stderr
        assert result.stderr == ""
        lines = result.stdout.splitlines()
        assert len(lines) == 1
        return json.loads(lines[0])

    def test_catalog_contract(self):
        data = self.parse_json(run("catalog"))
        part = next(p for p in data["parts"] if p["part"] == "3004.dat")
        assert (part["x_studs"], part["z_studs"]) == (2, 1)
        assert data["allowed_colours"]
        assert data["allowed_colours"] == sorted(data["allowed_colours"], key=lambda c: c["code"])
        assert all(set(("code", "name")) <= set(c) for c in data["allowed_colours"])

    def test_validate_and_analyze_contract(self):
        model = ROOT / "examples/reference_models/rotated-one-stud.json"
        valid = self.parse_json(run("validate", model))
        assert valid["valid"]
        analysis = self.parse_json(run("analyze", model))
        assert analysis["edges"] == [["base", "upper"]]
        assert analysis["root_id"] == "base"

    def test_invalid_and_disconnected_models_are_structured(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text(json.dumps({"schema_version": 1, "model_id": "Bad ID", "name": "bad", "parts": []}))
            data = self.parse_json(run("validate", path), 2)
            assert not (data["valid"])
            assert all(set(("code", "path", "message", "repair_hint")) <= set(i) for i in data["issues"])

            disconnected = {"schema_version": 1, "model_id": "disconnected", "name": "x", "parts": [
                {"id": "a", "part": "3005.dat", "colour": 4, "translation_ldu": [0, 0, 0], "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1]},
                {"id": "b", "part": "3005.dat", "colour": 1, "translation_ldu": [100, 0, 0], "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1]}]}
            path.write_text(json.dumps(disconnected))
            data = self.parse_json(run("validate", path), 2)
            assert any(i["code"] == "DISCONNECTED_ASSEMBLY" for i in data["issues"])

    def test_invalid_analyze_and_compile_are_structured(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "invalid.json"
            path.write_text("{}")
            assert not (self.parse_json(run("analyze", path), 2)["valid"])
            output = Path(d) / "should-not-exist.ldr"
            assert not (self.parse_json(run("compile", path, output), 2)["valid"])
            assert not (output.exists())

    def test_internal_handler_error_is_exit_three(self, monkeypatch, capsys):
        from brick_builder import cli
        def fail_catalog(args):
            raise RuntimeError("boom")

        monkeypatch.setattr(cli, "_catalog", fail_catalog)
        status = cli.main(["catalog"])
        assert status == 3
        payload = json.loads(capsys.readouterr().out)
        assert payload["issues"][0]["code"] == "INTERNAL_ERROR"

    def test_compile_hash_and_legacy_shim(self):
        model = ROOT / "examples/reference_models/rotated-one-stud.json"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "model.ldr"
            data = self.parse_json(run("compile", model, out))
            assert out.exists()
            assert data["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
            legacy = self.parse_json(run(model, Path(d) / "legacy.ldr"))
            assert legacy["valid"]

    def test_demo_generate_smoke_and_analysis_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "demo"
            data = self.parse_json(run("demo-generate", "tiny red wall", "--run-dir", run_dir))
            assert data["valid"]
            manifest = json.loads((run_dir / "manifest.json").read_text())
            assert manifest["outcome"] == "success"
            assert manifest["attempts"] == 1
            re.search(r"^[0-9a-f]{64}$", manifest["palette_sha256"])
            assert "software_version" in manifest
            analysis = json.loads((run_dir / "analysis-1.json").read_text())
            for field in ("edges", "bounds_ldu", "dimensions", "grounded_ids", "root_id", "collision_count", "disconnection_count"):
                assert field in analysis
            assert analysis["collision_count"] == 0

    def test_demo_generate_rejects_invalid_attempt_limit(self):
        with tempfile.TemporaryDirectory() as d:
            result = run("demo-generate", "wall", "--run-dir", Path(d) / "demo", "--max-attempts", "0")
            data = self.parse_json(result, 2)
            assert not (data["valid"])
            assert data["issues"][0]["code"] == "INPUT_ERROR"

    def test_manifest_command_invalid_inputs_are_structured(self):
        with tempfile.TemporaryDirectory() as d:
            missing = self.parse_json(run("manifest", Path(d) / "missing", "--outcome", "success", "--attempts", "1", "--max-attempts", "3"), 2)
            assert missing["issues"][0]["code"] == "INPUT_ERROR"
            root = Path(d) / "run"
            root.mkdir()
            invalid = self.parse_json(run("manifest", root, "--outcome", "nope", "--attempts", "4", "--max-attempts", "3"), 2)
            assert invalid["issues"][0]["code"] == "INPUT_ERROR"

    def test_manifest_command_writes_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "run"
            root.mkdir()
            artifact = root / "command-catalog.json"
            artifact.write_text('{"valid":true}\n')
            self.parse_json(run("manifest", root, "--outcome", "exhausted", "--attempts", "3", "--max-attempts", "3"))
            manifest = json.loads((root / "manifest.json").read_text())
            assert manifest["outcome"] == "exhausted"
            assert manifest["files"][artifact.name] == hashlib.sha256(artifact.read_bytes()).hexdigest()
