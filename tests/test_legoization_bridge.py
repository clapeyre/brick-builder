import pytest
from pathlib import Path

from brick_builder.legoization_bridge import legoize_accepted_box
from brick_builder.stepped_legoization_bridge import legoize_accepted_stepped_boxes
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept
from brick_builder.local_redesign import Block


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(*boxes):
    blocks = tuple(Block(ref, center, size, color) for ref, center, size, color in boxes)
    return GenericBoxConcept("bridge-test", "Bridge test", blocks, {
        "camera": "three-quarter", "geometry_refs": [block.id for block in blocks],
    })


class TestLEGOizationBridge:
    def test_one_grounded_box_maps_and_is_repeatable(self):
        value = concept(("box", (0, 2, 0), (4, 4, 2), "#2878b5"))
        first = legoize_accepted_box(value, PALETTE)
        second = legoize_accepted_box(value, PALETTE)
        assert first.success
        assert first.legoization.valid
        assert first.snapshot()["assembly"]["coverage_complete"]
        assert first.snapshot()["assembly"]["structural_valid"]
        assert first.serialize() == second.serialize()
        assert first.mapping["spatial_units"] == {"x": "stud", "y": "plate", "z": "stud"}

    def test_rejects_multi_box_non_integral_grounding_and_bounds(self):
        cases = [
            (concept(("a", (0, 1, 0), (2, 2, 1), "#2878b5"), ("b", (0, 3, 0), (2, 2, 1), "#2878b5")), "MULTI_BOX_UNSUPPORTED"),
            (concept(("a", (0, 1.25, 0), (2.5, 2, 1), "#2878b5")), "NON_INTEGRAL_DIMENSION"),
            (concept(("a", (0, 0, 0), (2, 2, 1), "#2878b5")), "NOT_GROUNDED"),
            (concept(("a", (0, 9, 0), (18, 18, 1), "#2878b5")), "OUT_OF_BOUNDS"),
        ]
        for candidate, code in cases:
            result = legoize_accepted_box(candidate, PALETTE)
            assert not (result.success)
            assert result.legoization is None
            assert any(code in diagnostic for diagnostic in result.diagnostics)

    def test_source_concept_is_preserved_in_serialized_result(self):
        result = legoize_accepted_box(concept(("box", (0, 1, 0), (2, 2, 2), "#2878b5")), PALETTE)
        assert result.snapshot()["source_concept"]["geometry"][0]["ref"] == "box"
        assert "compiled_ldr" in result.snapshot()["assembly"]

    def test_supported_green_maps_to_ldraw_code_two(self):
        result = legoize_accepted_box(concept(("box", (0, 1, 0), (2, 2, 2), "#2e8b57")), PALETTE)
        assert result.success
        assert result.mapping["source_color"] == "#2e8b57"
        assert result.mapping["mapped_colour"] == 2
        assert all(line.split()[1] == "2" for line in result.compiled_ldr.splitlines() if line.startswith("1 "))

    @pytest.mark.parametrize("colour, diagnostic", [("#123456", "COLOUR_UNSUPPORTED")])
    def test_rejects_source_colour_that_is_not_supported(self, colour, diagnostic):
        result = legoize_accepted_box(concept(("box", (0, 1, 0), (2, 2, 2), colour)), PALETTE)
        assert not result.success
        assert result.mapping is None
        assert any(diagnostic in item for item in result.diagnostics)

    def test_rejects_mixed_colours_as_ambiguous(self):
        value = GenericBoxConcept(
            "bridge-test", "Bridge test",
            (Block("base", (0, 1, 0), (4, 2, 2), "#237841"), Block("upper", (0, 3, 0), (2, 2, 2), "#c91a09")),
            {"camera": "three-quarter", "geometry_refs": ["base", "upper"]},
        )
        result = legoize_accepted_stepped_boxes(value, PALETTE)
        assert not result.success
        assert any("COLOUR_AMBIGUOUS" in item for item in result.diagnostics)

    def test_source_green_maps_to_palette_and_every_part(self):
        result = legoize_accepted_box(concept(("box", (0, 2, 0), (4, 4, 2), "#2ca02c")), PALETTE)
        assert result.success
        assert result.mapping["source_color"] == "#2ca02c"
        assert result.mapping["mapped_colour"] == 2
        assert {part["colour"] for part in result.legoization.model["parts"]} == {2}

    def test_unsupported_source_colour_is_rejected_without_fallback(self):
        result = legoize_accepted_box(concept(("box", (0, 1, 0), (2, 2, 2), "#123456")), PALETTE)
        assert not result.success
        assert result.legoization is None
        assert any("COLOUR_UNSUPPORTED" in diagnostic for diagnostic in result.diagnostics)
