import pytest
from pathlib import Path

from brick_builder.candidate_composition import CandidateCompositionError, compose_candidate_set, select_candidate
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept

ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier, *boxes):
    return GenericBoxConcept(identifier, identifier, tuple(Block(*box) for box in boxes),
                              {"camera": "three-quarter", "geometry_refs": [box[0] for box in boxes]})


class TestCandidateComposition:
    def test_dispatches_all_supported_families_without_selection(self):
        result = compose_candidate_set("make a small set", [
            concept("box", ("b", (0, 1, 0), (2, 2, 2), "#2878b5")),
            concept("step", ("base", (0, .5, 0), (4, 1, 2), "#2878b5"), ("upper", (0, 1.5, 0), (2, 1, 2), "#2878b5")),
            concept("gate", ("bridge", (0, 1.5, 0), (6, 1, 2), "#2878b5"), ("right", (2, .5, 0), (2, 1, 2), "#2878b5"), ("left", (-2, .5, 0), (2, 1, 2), "#2878b5")),
        ], PALETTE)
        assert result.success
        assert [item["family"] for item in result.candidates] == ["one-box", "stepped-box", "gatehouse"]
        assert "selected" not in result.snapshot()

    def test_preserves_request_and_hashes_and_selection_provenance(self):
        concepts = [concept("first", ("box", (0, 1, 0), (2, 2, 2), "#2878b5")), concept("second", ("box", (0, 1, 0), (4, 2, 2), "#2878b5"))]
        first = compose_candidate_set("raw request exactly", concepts, PALETTE)
        second = compose_candidate_set("raw request exactly", concepts, PALETTE)
        assert first.serialize() == second.serialize()
        assert first.request_text == "raw request exactly"
        receipt = select_candidate(first, "second")
        assert receipt["candidate_set_hash"] == first.candidate_set_hash
        assert receipt["selected_candidate_id"] == "second"
        assert receipt["source_concept_id"] == "second"

    def test_rejects_duplicates_unsupported_and_failed_sets_without_auto_selection(self):
        duplicate = concept("same", ("box", (0, 1, 0), (2, 2, 2), "#2878b5"))
        result = compose_candidate_set("request", [duplicate, duplicate], PALETTE)
        assert not (result.success)
        assert any("DUPLICATE_ID" in d for d in result.candidates[1]["diagnostics"])
        with pytest.raises(CandidateCompositionError):
            select_candidate(result, "same")
        unsupported = compose_candidate_set("request", [
            concept("bad", *(tuple((f"b{i}", (0, i + 1, 0), (2, 1, 1), "#2878b5") for i in range(4)))),
            concept("good", ("box", (0, 1, 0), (2, 2, 2), "#2878b5")),
        ], PALETTE)
        assert not (unsupported.success)
        assert "UNSUPPORTED_SHAPE" in unsupported.candidates[0]["diagnostics"][0]

    def test_rejects_duplicate_geometry_independent_of_identity_metadata_and_order(self):
        first = GenericBoxConcept(
            "green-compact-beam",
            "Compact beam",
            (
                Block("beam", (0, 0.5, 0), (4, 1, 2), "#2e8b57"),
                Block("pier-b", (0, 1.5, 0), (2, 1, 2), "#2e8b57"),
            ),
            {"camera": "front", "geometry_refs": ["beam", "pier-b"]},
        )
        duplicate = GenericBoxConcept(
            "green-wide-deck",
            "Wide deck",
            (
                Block("support", (0.0, 1.5, 0.0), (2.0, 1.0, 2.0), "#d71920"),
                Block("deck", (0.0, 0.5, 0.0), (4.0, 1.0, 2.0), "#d71920"),
            ),
            {"camera": "top", "geometry_refs": ["support", "deck"]},
        )
        distinct = concept("green-two-pier", ("deck", (0, 1, 0), (2, 2, 2), "#2e8b57"))

        result = compose_candidate_set("A small green beam bridge", [first, duplicate, distinct], PALETTE)

        assert result.status == "rejected"
        assert [item["id"] for item in result.candidates] == [
            "green-compact-beam", "green-wide-deck", "green-two-pier"
        ]
        assert result.candidates[0]["status"] == "success"
        assert result.candidates[1]["status"] == "failed"
        assert result.candidates[1]["geometry_hash"] == result.candidates[0]["geometry_hash"]
        assert "DUPLICATE_GEOMETRY:" in result.candidates[1]["diagnostics"][0]
        assert "geometry hash" in result.candidates[1]["diagnostics"][0]
        assert result.candidates[2]["status"] == "success"
        assert "bridge" not in result.candidates[1]

    def test_geometry_hash_is_deterministic_and_does_not_select_or_rank(self):
        concepts = [
            concept("first", ("box", (0, 1, 0), (2, 2, 2), "#2878b5")),
            concept("second", ("box", (0, 1, 0), (4, 2, 2), "#2878b5")),
        ]
        first = compose_candidate_set("same request", concepts, PALETTE)
        second = compose_candidate_set("same request", concepts, PALETTE)

        assert first.candidate_set_hash == second.candidate_set_hash
        assert [item["id"] for item in first.candidates] == ["first", "second"]
        assert [item["geometry_hash"] for item in first.candidates] == [
            item["geometry_hash"] for item in second.candidates
        ]
        assert "selected" not in first.snapshot()
