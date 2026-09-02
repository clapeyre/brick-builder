import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.spatial_concept import SpatialConceptError, SpatialConceptSession, render_concept, write_session_artifacts


def response(kind="concepts"):
    concepts = []
    for concept_index in range(2):
        concepts.append({
            "id": f"concept-{concept_index + 1}",
            "label": f"box idea {concept_index + 1}",
            "geometry": [{
                "ref": f"concept-{concept_index + 1}/box-1",
                "center": [concept_index * 2, 0, 0],
                "size": [4, 2, 3],
                "color": "#2878b5",
            }],
            "render": {
                "camera": "three-quarter",
                "width": 430,
                "height": 360,
                "scale": 24,
                "geometry_refs": [f"concept-{concept_index + 1}/box-1"],
            },
        })
    return {"kind": kind, "concepts": concepts}


class SpatialConceptSessionTests(unittest.TestCase):
    def test_success_preserves_request_and_returns_stable_bounded_concepts(self):
        request = "  Make me a friendly little rover!  "
        session = SpatialConceptSession(request)
        result = session.submit(response())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["request_text"], request)
        self.assertEqual(len(result["concepts"]), 2)
        self.assertEqual(result["concepts"][0]["geometry"][0]["ref"], "concept-1/box-1")
        self.assertEqual(result["concepts"][0]["render"]["geometry_refs"], ["concept-1/box-1"])

    def test_clarification_is_a_terminal_actionable_result(self):
        session = SpatialConceptSession("Build something fun")
        result = session.submit({"kind": "clarification", "question": "Should it be a vehicle or a creature?"})
        self.assertEqual(result["status"], "clarification")
        self.assertEqual(result["clarification"], "Should it be a vehicle or a creature?")
        with self.assertRaises(SpatialConceptError):
            session.submit(response())

    def test_malformed_and_out_of_bounds_responses_exhaust_fixed_attempts(self):
        session = SpatialConceptSession("Make a tower")
        malformed = {"kind": "concepts", "concepts": [{"id": "only-one"}]}
        for attempt in range(2):
            result = session.submit(malformed)
            self.assertEqual(result["status"], "pending")
            self.assertEqual(result["attempts"], attempt + 1)
            self.assertTrue(result["feedback"])
        bad = response()
        bad["concepts"][0]["geometry"][0]["size"] = [100, 2, 3]
        result = session.submit(bad)
        self.assertEqual(result["status"], "exhausted")
        self.assertEqual(result["attempts"], 3)
        with self.assertRaises(SpatialConceptError):
            session.submit(response())

    def test_concept_ids_cannot_escape_render_artifact_root(self):
        bad = response()
        bad["concepts"][0]["id"] = "../outside"
        session = SpatialConceptSession("Make a tower")
        result = session.submit(bad)
        self.assertEqual(result["status"], "pending")
        self.assertIn("concept 1.id", result["feedback"][0])

    def test_serialization_is_deterministic(self):
        session = SpatialConceptSession("A boxy boat")
        session.submit(response())
        encoded = session.serialize()
        self.assertEqual(encoded, session.serialize())
        self.assertEqual(json.loads(encoded), session.snapshot())
        self.assertNotIn("  ", encoded)

    def test_success_writes_reproducible_previews_and_session_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            session = SpatialConceptSession("Make a boxy boat")
            session.submit(response())
            first = write_session_artifacts(session, Path(directory) / "one")
            second = write_session_artifacts(session, Path(directory) / "two")
            self.assertEqual(first["renders"], second["renders"])
            self.assertEqual(
                (Path(directory) / "one" / "render-concept-1.svg").read_bytes(),
                (Path(directory) / "two" / "render-concept-1.svg").read_bytes(),
            )
            self.assertEqual(first["request_text"], "Make a boxy boat")
            self.assertTrue(first["renders"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
