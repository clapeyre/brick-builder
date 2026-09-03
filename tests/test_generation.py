import hashlib
import json
import tempfile
import pytest
from pathlib import Path

from brick_builder.generation import finalize_manifest, generate
from brick_builder.palette import load_palette

ROOT = Path(__file__).parents[1]
PALETTE = ROOT / "brick_builder/palettes/classic-core-v0.json"
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1]


def valid_model():
    return {"schema_version": 1, "model_id": "fake", "name": "Fake", "parts": [
        {"id": "a", "part": "3001.dat", "colour": 4, "translation_ldu": [0, 0, 0], "matrix": IDENTITY},
        {"id": "b", "part": "3001.dat", "colour": 1, "translation_ldu": [0, -24, 0], "matrix": IDENTITY}]}


class Fake:
    def __init__(self, values): self.values, self.calls = values, []
    def generate(self, request, attempt, feedback):
        self.calls.append(feedback)
        return self.values[attempt - 1]


class TestGeneration:
    def test_first_attempt_success_and_complete_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            result = generate("wall", PALETTE, Path(d) / "run", Fake([valid_model()]))
            assert result.valid
            manifest = json.loads((result.run_dir / "manifest.json").read_text())
            assert (result.run_dir / "final.json").exists()
            assert (result.run_dir / "final.ldr").exists()
            for name, digest in manifest["files"].items():
                assert digest == hashlib.sha256((result.run_dir / name).read_bytes()).hexdigest()
            assert (result.run_dir / "spec.json").exists()
            assert (result.run_dir / "analysis-1.json").exists()

    def test_repair_success_passes_human_feedback(self):
        bad = valid_model(); bad["parts"][1]["translation_ldu"] = [100, 0, 0]
        fake = Fake([bad, valid_model()])
        with tempfile.TemporaryDirectory() as d:
            result = generate("wall", PALETTE, Path(d) / "run", fake)
        assert result.valid; assert result.attempts == 2
        assert len(fake.calls) == 2
        assert fake.calls[0] == []
        assert fake.calls[1]; assert "repair_hint" in fake.calls[1][0]; assert fake.calls[1][0]["repair_hint"] != fake.calls[1][0]["code"]

    def test_exhaustion_has_no_final_files_and_unique_clean_dir(self):
        bad = valid_model(); bad["parts"][1]["translation_ldu"] = [100, 0, 0]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "run"; root.mkdir(); (root / "stale.txt").write_text("stale")
            result = generate("wall", PALETTE, root, Fake([bad, bad]), max_attempts=2)
            assert not (result.valid); assert result.attempts == 2
            assert not ((result.run_dir / "final.json").exists()); assert not ((result.run_dir / "final.ldr").exists())
            assert not ((result.run_dir / "stale.txt").exists())

    def test_invalid_attempt_limit_fails_before_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "run"
            for value in (0, -1):
                with pytest.raises(ValueError): generate("wall", PALETTE, root, max_attempts=value)
            assert not (root.exists())

    def test_adapter_never_receives_attempt_beyond_bound(self):
        bad = valid_model(); bad["parts"][1]["translation_ldu"] = [100, 0, 0]
        fake = Fake([bad, bad, bad])
        with tempfile.TemporaryDirectory() as d:
            result = generate("wall", PALETTE, Path(d) / "run", fake, max_attempts=2)
        assert not (result.valid)
        assert len(fake.calls) == 2

    def test_finalize_manifest_hashes_regular_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "run"
            root.mkdir()
            (root / "request.txt").write_text("wall\n")
            (root / "candidate-1.json").write_text("{}")
            (root / "nested").mkdir()
            manifest = finalize_manifest(root, outcome="success", attempts=1, max_attempts=3, palette_path=PALETTE)
            assert "candidate-1.json" in manifest["files"]
            assert "manifest.json" not in manifest["files"]
            assert "nested" not in manifest["files"]
            assert manifest["request_sha256"] == hashlib.sha256((root / "request.txt").read_bytes()).hexdigest()
            assert manifest["palette_sha256"] == hashlib.sha256(json.dumps(load_palette(PALETTE), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
