import json
import tempfile
import pytest
from pathlib import Path

from brick_builder.candidate_composition import compose_candidate_set
from brick_builder.candidate_rendering import render_candidate_set
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier, width=2):
    return GenericBoxConcept(
        identifier,
        identifier,
        (Block("box", (0, 1, 0), (width, 2, 2), "#2878b5"),),
        {"camera": "three-quarter", "geometry_refs": ["box"]},
    )


class TestCandidateRendering:
    def test_successful_candidates_get_deterministic_fixed_camera_evidence(self):
        candidate_set = compose_candidate_set("render these", [concept("first"), concept("second", 4)], PALETTE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for candidate in candidate_set.candidates:
                (root / "candidates" / candidate["id"]).mkdir(parents=True, exist_ok=True)
            first = render_candidate_set(candidate_set.snapshot(), root, PALETTE)
            bytes_one = (root / "candidates/first/render-evidence.json").read_bytes()
            second = render_candidate_set(candidate_set.snapshot(), root, PALETTE)
            assert first == second
            assert bytes_one == (root / "candidates/first/render-evidence.json").read_bytes()
            assert [render["camera_id"] for render in first["candidates"][0]["renders"]] == ["front", "three-quarter"]
            assert (root / "candidates/first/render-front.svg").is_file()

    def test_rejected_candidates_remain_indexed_without_render_artifacts(self):
        unsupported = GenericBoxConcept(
            "unsupported",
            "unsupported",
            tuple(Block(f"box-{index}", (0, index + 0.5, 0), (2, 1, 2), "#2878b5") for index in range(4)),
            {"camera": "three-quarter", "geometry_refs": [f"box-{index}" for index in range(4)]},
        )
        candidate_set = compose_candidate_set("render these", [concept("first"), unsupported], PALETTE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for candidate in candidate_set.candidates:
                (root / "candidates" / candidate["id"]).mkdir(parents=True, exist_ok=True)
            result = render_candidate_set(candidate_set.snapshot(), root, PALETTE)
            assert result["status"] == "rejected"
            assert [item["status"] for item in result["candidates"]] == ["success", "failed"]
            assert (root / "candidates/first/render-evidence.json").is_file()
            assert "render_evidence" not in result["candidates"][1]
            assert not ((root / "candidates/unsupported/render-evidence.json").exists())
