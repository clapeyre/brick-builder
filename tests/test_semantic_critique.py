import json
import tempfile
import pytest
from pathlib import Path

from brick_builder.candidate_composition import compose_candidate_set
from brick_builder.candidate_rendering import render_candidate_set
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.semantic_critique import (
    FIXTURE_FORMAT,
    FORMAT,
    SemanticCritiqueError,
    evaluate_semantic_critique,
)
from brick_builder.spatial_concept import GenericBoxConcept
from brick_builder.visual_critique import critique_candidate_set


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier="tower", width=4):
    return GenericBoxConcept(identifier, identifier, (Block("box", (0, 1, 0), (width, 2, 2), "#2878b5"),), {"camera": "three-quarter", "geometry_refs": ["box"]})


def evidence_fixture():
    with tempfile.TemporaryDirectory() as directory:
        composition = compose_candidate_set("make a small blue tower", [concept(), concept("other", 6)], PALETTE)
        for candidate in composition.candidates:
            child = Path(directory) / "candidates" / candidate["id"]
            child.mkdir(parents=True)
            child.joinpath("final.ldr").write_text(candidate["bridge"]["assembly"]["compiled_ldr"], encoding="utf-8")
        rendering = render_candidate_set(composition.snapshot(), directory, PALETTE)
        critique = critique_candidate_set(rendering).snapshot()
        return composition, critique


FIXTURE = {
    "format": FIXTURE_FORMAT,
    "expected": {
        "identity": {"family": "one-box"},
        "silhouette": {"camera_id": "three-quarter", "aspect": {"min": 0.1, "max": 10.0}},
        "landmarks": {"camera_id": "three-quarter", "required": [{"id": "missing-detail", "visible": True}]},
        "proportions": {"camera_id": "three-quarter", "aspect": {"min": 0.1, "max": 10.0}},
        "symmetry": {"required": True},
        "accidental_artifacts": {"forbid": ["floating-shadow"]},
    },
}


class TestSemanticCritique:
    def test_fixture_emits_satisfied_and_unsatisfied_bounded_findings(self):
        composition, critique = evidence_fixture()
        artifact = evaluate_semantic_critique(composition, "tower", critique, FIXTURE).snapshot()
        assert artifact["format"] == FORMAT
        assert artifact["dimensions"]["identity"]["status"] == "observed"
        assert artifact["dimensions"]["landmarks"]["status"] == "missing"
        assert artifact["dimensions"]["symmetry"]["status"] == "not-assessed"
        assert artifact["engineering_validation"]["valid"]
        assert artifact["dimensions"]["silhouette"]["source_evidence"]
        assert not (artifact["semantic_resemblance_evaluated"])
        encoded = json.dumps(artifact).lower()
        for forbidden in ("score", "rank", "winner", "preference", "repair"):
            assert forbidden not in encoded

    def test_fixed_evidence_is_deterministic(self):
        composition, critique = evidence_fixture()
        first = evaluate_semantic_critique(composition, "tower", critique, FIXTURE).serialize()
        second = evaluate_semantic_critique(composition, "tower", critique, FIXTURE).serialize()
        assert first == second
        with tempfile.TemporaryDirectory() as directory:
            path = evaluate_semantic_critique(composition, "tower", critique, FIXTURE).write(
                Path(directory) / "semantic-critique.json"
            )
            assert path.read_text(encoding="utf-8").rstrip("\n") == first

    def test_rejects_malformed_or_unsupported_fixture_actionably(self):
        composition, critique = evidence_fixture()
        with pytest.raises(SemanticCritiqueError, match="unsupported dimensions"):
            evaluate_semantic_critique(composition, "tower", critique, {"format": FIXTURE_FORMAT, "expected": {**FIXTURE["expected"], "mood": {}}})
        with pytest.raises(SemanticCritiqueError, match="unsupported keys"):
            evaluate_semantic_critique(composition, "tower", critique, {"format": FIXTURE_FORMAT, "expected": {**FIXTURE["expected"], "identity": {"family": "one-box", "mood": "happy"}}})
        malformed = {"format": FIXTURE_FORMAT, "expected": {name: {} for name in FIXTURE["expected"]}}
        malformed["expected"]["silhouette"] = {"camera_id": "three-quarter", "aspect": {"min": 3, "max": 1}}
        with pytest.raises(SemanticCritiqueError, match="must not exceed"):
            evaluate_semantic_critique(composition, "tower", critique, malformed)

    def test_requires_successful_existing_evidence(self):
        composition, critique = evidence_fixture()
        failed = dict(composition.snapshot(), status="rejected")
        with pytest.raises(SemanticCritiqueError, match="status 'success'"):
            evaluate_semantic_critique(failed, "tower", critique, FIXTURE)
        with pytest.raises(SemanticCritiqueError, match="visual_critique must use"):
            evaluate_semantic_critique(composition, "tower", {"format": "other"}, FIXTURE)
