import json
import unittest

from brick_builder.visual_critique import VisualCritiqueError, critique_candidate_set


def record(identifier, evidence, *, parts=("p1", "p2")):
    return {
        "id": identifier,
        "status": "success",
        "model_id": identifier + "-model",
        "part_ids": list(parts),
        "landmarks": [{"id": "front-detail", "part_ids": [parts[0]]}],
        "render_evidence": evidence,
    }


EVIDENCE = {
    "schema_version": 1,
    "renders": [
        {
            "camera_id": "front", "file": "render-front.svg", "sha256": "a" * 64,
            "rendered_part_ids": ["p1"],
            "visible_polygon_count": 3,
            "non_background_bounds": {"x": [10, 210], "y": [20, 120]},
        },
        {
            "camera_id": "three-quarter", "file": "render-three-quarter.svg", "sha256": "b" * 64,
            "rendered_part_ids": ["p1", "p2"],
            "visible_polygon_count": 6,
            "non_background_bounds": {"x": [0, 320], "y": [0, 240]},
        },
    ],
}


class VisualCritiqueTests(unittest.TestCase):
    def test_is_stable_and_contains_references_and_bounded_observations(self):
        source = {"status": "success", "candidates": [record("one", EVIDENCE)]}
        first = critique_candidate_set(source)
        second = critique_candidate_set(source)
        self.assertEqual(first.serialize(), second.serialize())
        front = first.snapshot()["candidates"][0]["cameras"][0]
        self.assertEqual(front["evidence"]["file"], "render-front.svg")
        self.assertEqual(front["observations"]["silhouette"]["occupancy"], round(200 * 100 / (640 * 480), 6))
        self.assertEqual(front["observations"]["silhouette"]["aspect"], 2.0)
        self.assertEqual(front["observations"]["part_visibility"], {"p1": True, "p2": False})
        self.assertEqual(front["observations"]["landmark_visibility"], {"front-detail": True})

    def test_accepts_equivalent_records_with_external_evidence(self):
        result = critique_candidate_set(
            [record("one", None)],
            render_evidence_by_candidate={"one": EVIDENCE},
        )
        self.assertEqual([item["id"] for item in result.snapshot()["candidates"]], ["one"])

    def test_accepts_rendering_index_reference_with_inline_renders(self):
        rendering_record = record("one", None)
        rendering_record.pop("render_evidence")
        rendering_record.update({
            "render_evidence": "candidates/one/render-evidence.json",
            "renders": EVIDENCE["renders"],
        })
        result = critique_candidate_set([rendering_record])
        self.assertEqual(
            result.snapshot()["candidates"][0]["cameras"][0]["evidence"]["artifact"],
            "candidates/one/render-evidence.json",
        )

    def test_rejects_unsuccessful_or_missing_evidence_actionably(self):
        with self.assertRaisesRegex(VisualCritiqueError, "status 'success'"):
            critique_candidate_set({"status": "failed", "candidates": []})
        with self.assertRaisesRegex(VisualCritiqueError, "no render evidence"):
            critique_candidate_set([record("one", None)])

    def test_does_not_emit_ranking_or_selection_fields(self):
        snapshot = critique_candidate_set({"status": "success", "candidates": [record("one", EVIDENCE)]}).snapshot()
        self.assertNotIn("rank", json.dumps(snapshot))
        self.assertNotIn("selected", json.dumps(snapshot))


if __name__ == "__main__":
    unittest.main()
