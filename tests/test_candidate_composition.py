import unittest
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


class CandidateCompositionTests(unittest.TestCase):
    def test_dispatches_all_supported_families_without_selection(self):
        result = compose_candidate_set("make a small set", [
            concept("box", ("b", (0, 1, 0), (2, 2, 2), "#2878b5")),
            concept("step", ("base", (0, .5, 0), (4, 1, 2), "#2878b5"), ("upper", (0, 1.5, 0), (2, 1, 2), "#2878b5")),
            concept("gate", ("bridge", (0, 1.5, 0), (6, 1, 2), "#2878b5"), ("right", (2, .5, 0), (2, 1, 2), "#2878b5"), ("left", (-2, .5, 0), (2, 1, 2), "#2878b5")),
        ], PALETTE)
        self.assertTrue(result.success)
        self.assertEqual([item["family"] for item in result.candidates], ["one-box", "stepped-box", "gatehouse"])
        self.assertNotIn("selected", result.snapshot())

    def test_preserves_request_and_hashes_and_selection_provenance(self):
        concepts = [concept("first", ("box", (0, 1, 0), (2, 2, 2), "#2878b5")), concept("second", ("box", (0, 1, 0), (4, 2, 2), "#2878b5"))]
        first = compose_candidate_set("raw request exactly", concepts, PALETTE)
        second = compose_candidate_set("raw request exactly", concepts, PALETTE)
        self.assertEqual(first.serialize(), second.serialize())
        self.assertEqual(first.request_text, "raw request exactly")
        receipt = select_candidate(first, "second")
        self.assertEqual(receipt["candidate_set_hash"], first.candidate_set_hash)
        self.assertEqual(receipt["selected_candidate_id"], "second")
        self.assertEqual(receipt["source_concept_id"], "second")

    def test_rejects_duplicates_unsupported_and_failed_sets_without_auto_selection(self):
        duplicate = concept("same", ("box", (0, 1, 0), (2, 2, 2), "#2878b5"))
        result = compose_candidate_set("request", [duplicate, duplicate], PALETTE)
        self.assertFalse(result.success)
        self.assertTrue(any("DUPLICATE_ID" in d for d in result.candidates[1]["diagnostics"]))
        with self.assertRaises(CandidateCompositionError):
            select_candidate(result, "same")
        unsupported = compose_candidate_set("request", [
            concept("bad", *(tuple((f"b{i}", (0, i + 1, 0), (2, 1, 1), "#2878b5") for i in range(4)))),
            concept("good", ("box", (0, 1, 0), (2, 2, 2), "#2878b5")),
        ], PALETTE)
        self.assertFalse(unsupported.success)
        self.assertIn("UNSUPPORTED_SHAPE", unsupported.candidates[0]["diagnostics"][0])


if __name__ == "__main__":
    unittest.main()
