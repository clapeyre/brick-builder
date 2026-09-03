import json
import os
import tempfile
import pytest
from pathlib import Path

from brick_builder.compiler import compile_model
from brick_builder.ldraw import LDrawDiscoveryError, discover_ldraw_library
from brick_builder.palette import load_palette
from brick_builder.validation import ValidationError, validate_model


ROOT = Path(__file__).parents[1]
PALETTE_PATH = ROOT / "brick_builder" / "palettes" / "classic-core-v0.json"


def reference(name):
    return json.loads((ROOT / "examples" / "reference_models" / name).read_text())


class TestFoundation:
    def setup_method(self):
        self.palette = load_palette(PALETTE_PATH)

    def test_palette_loads_with_expected_vocabulary(self):
        assert self.palette["schema_version"] == 1
        assert "3001.dat" in {part["ldraw_file"] for part in self.palette["parts"]}
        assert 4 in {colour["ldraw_code"] for colour in self.palette["colours"]}

    def test_reference_models_validate(self):
        for filename in ("tiny-red-wall.json", "tiny-blue-step.json", "rotated-one-stud.json"):
            validate_model(reference(filename), self.palette)

    def test_step_reference_keeps_the_small_plate_centered_on_the_base(self):
        model = reference("tiny-blue-step.json")
        assert model["parts"][1]["translation_ldu"] == [0, -8, 10]

    def test_invalid_part_colour_translation_and_rotation_are_reported(self):
        model = reference("tiny-red-wall.json")
        model["parts"][0].update({
            "part": "NOT-A-PART.DAT",
            "colour": 999,
            "translation_ldu": [0, 1.5, 0],
            "matrix": [1, 1, 0, 0, 1, 0, 0, 0, 1],
        })
        with pytest.raises(ValidationError) as raised:
            validate_model(model, self.palette)
        message = str(raised.value)
        assert "parts[0].part" in message
        assert "parts[0].colour" in message
        assert "parts[0].translation_ldu" in message
        assert "parts[0].matrix" in message

    def test_reflection_is_not_a_permitted_rotation(self):
        model = reference("tiny-red-wall.json")
        model["parts"][0]["matrix"] = [-1, 0, 0, 0, 1, 0, 0, 0, 1]
        with pytest.raises(ValidationError):
            validate_model(model, self.palette)

    def test_compiler_is_deterministic_and_emits_type_one_lines(self):
        model = reference("tiny-red-wall.json")
        with tempfile.TemporaryDirectory() as directory:
            first = compile_model(model, Path(directory) / "one.ldr", self.palette).read_text()
            second = compile_model(model, Path(directory) / "two.ldr", self.palette).read_text()
        assert first == second
        assert "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat" in first

    def test_compiler_emits_rotated_reference(self):
        model = reference("rotated-one-stud.json")
        with tempfile.TemporaryDirectory() as directory:
            output = compile_model(model, Path(directory) / "rotated.ldr", self.palette).read_text()
        assert "1 1 10 -24 20 0 0 1 0 1 0 -1 0 0 3004.dat" in output

    def test_discovery_honours_explicit_override_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "parts").mkdir()
            (root / "parts" / "3001.dat").write_text("0 Brick 2 x 4\n")
            (root / "LDConfig.ldr").write_text("0 !LDRAW_ORG Configuration UPDATE 2024\n")
            found = discover_ldraw_library(root)
            assert found.root == root.resolve()

    def test_discovery_reports_missing_library(self):
        with pytest.raises(LDrawDiscoveryError):
            discover_ldraw_library("Z:\\definitely-not-a-library")
