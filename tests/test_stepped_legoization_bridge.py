import pytest
from pathlib import Path

from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept
from brick_builder.stepped_legoization_bridge import legoize_accepted_stepped_boxes


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(*boxes):
    return GenericBoxConcept(
        "stepped-bridge-test", "Stepped bridge test",
        tuple(Block(*box) for box in boxes),
        {"camera": "three-quarter", "geometry_refs": [box[0] for box in boxes]},
    )


class TestSteppedLEGOizationBridge:
    def test_two_aligned_tiers_map_deterministically(self):
        value = concept(
            ("upper", (0, 1.5, 0), (2, 1, 2), "#2878b5"),
            ("base", (0, 0.5, 0), (4, 1, 2), "#2878b5"),
        )
        first = legoize_accepted_stepped_boxes(value, PALETTE)
        second = legoize_accepted_stepped_boxes(value, PALETTE)
        assert first.success
        assert first.legoization.valid
        assert first.snapshot()["assembly"]["coverage_complete"]
        assert first.snapshot()["assembly"]["structural_valid"]
        assert first.serialize() == second.serialize()
        assert first.mapping["spatial_units"] == {"x": "stud", "y": "brick", "z": "stud"}

    def test_rejects_overlap_depth_and_non_integral_dimensions_without_assembly(self):
        cases = [
            (concept(("a", (0, 0.5, 0), (4, 1, 2), "#2878b5"), ("b", (0, 0.75, 0), (2, 1, 2), "#2878b5")), "OVERLAPPING_TIERS"),
            (concept(("a", (0, 0.5, 0), (4, 1, 3), "#2878b5"), ("b", (0, 2, 0), (2, 2, 3), "#2878b5")), "OUT_OF_BOUNDS"),
            (concept(("a", (0, 0.5, 0), (4.5, 1, 2), "#2878b5"), ("b", (0, 2, 0), (2, 1, 2), "#2878b5")), "NON_INTEGRAL_DIMENSION"),
        ]
        for candidate, code in cases:
            result = legoize_accepted_stepped_boxes(candidate, PALETTE)
            assert not (result.success)
            assert result.legoization is None
            assert any(code in diagnostic for diagnostic in result.diagnostics)

    def test_requires_exactly_two_and_reports_source_mapping(self):
        result = legoize_accepted_stepped_boxes(concept(("only", (0, 1, 0), (2, 2, 2), "#2878b5")), PALETTE)
        assert not (result.success)
        assert result.mapping is None
        assert result.snapshot()["source_concept"]["geometry"][0]["ref"] == "only"
        assert "TWO_BOXES_REQUIRED" in result.diagnostics[0]
