import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.candidate_composition import compose_candidate_set
from brick_builder.critique_operations import (
    FORMAT,
    CritiqueOperationError,
    evaluate_critique_operation,
)
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept
from brick_builder.candidate_rendering import render_candidate_set
from brick_builder.visual_critique import critique_candidate_set


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier="baseline", width=4):
    return GenericBoxConcept(identifier, identifier, (Block("box", (0, 1, 0), (width, 2, 2), "#2878b5"),),
                             {"camera": "three-quarter", "geometry_refs": ["box"]})


def fixture():
    """Checked-in-style offline fixture: prompt, observations, and one operation."""
    with tempfile.TemporaryDirectory() as directory:
        result = compose_candidate_set("make a small blue tower", [concept(), concept("other", 6)], PALETTE)
        for candidate in result.candidates:
            child = Path(directory) / "candidates" / candidate["id"]
            child.mkdir(parents=True)
            child.joinpath("final.ldr").write_text(
                candidate["bridge"]["assembly"]["compiled_ldr"], encoding="utf-8"
            )
        rendering = render_candidate_set(result.snapshot(), directory, PALETTE)
        critique = critique_candidate_set(rendering).snapshot()
        return result, critique, {
            "name": "recolor",
            "parameters": {"block_id": "box", "color": "red"},
        }


class CritiqueOperationTests(unittest.TestCase):
    def test_fixture_records_traceability_validity_and_no_semantic_score(self):
        result, critique, operation = fixture()
        evaluation = evaluate_critique_operation(result, "baseline", critique, operation, PALETTE)
        artifact = evaluation.snapshot()
        self.assertEqual(artifact["format"], FORMAT)
        self.assertTrue(evaluation.success)
        self.assertTrue(artifact["result"]["engineering_validation"]["valid"])
        self.assertEqual(artifact["traceability"]["baseline_candidate_set_hash"], result.candidate_set_hash)
        self.assertFalse(artifact["comparison"]["semantic_resemblance_evaluated"])
        self.assertNotIn("score", json.dumps(artifact).lower())

    def test_fixed_input_is_byte_identical(self):
        result, critique, operation = fixture()
        evaluation = evaluate_critique_operation(result, "baseline", critique, operation, PALETTE)
        first = evaluation.serialize()
        second = evaluate_critique_operation(result, "baseline", critique, operation, PALETTE).serialize()
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as directory:
            artifact_path = evaluation.write(Path(directory) / "critique-operation.json")
            self.assertEqual(artifact_path.read_text(encoding="utf-8").rstrip("\n"), first)

    def test_unknown_or_unbounded_operation_is_actionably_rejected(self):
        result, critique, _ = fixture()
        with self.assertRaisesRegex(CritiqueOperationError, "not allowlisted"):
            evaluate_critique_operation(result, "baseline", critique, {"name": "stretch-tail", "parameters": {}}, PALETTE)
        with self.assertRaisesRegex(CritiqueOperationError, "from 1 to 2"):
            evaluate_critique_operation(result, "baseline", critique, {"name": "increase-height", "parameters": {"plates": 99}}, PALETTE)

    def test_failed_revalidation_preserves_baseline_and_reports_regression(self):
        result, critique, _ = fixture()
        evaluation = evaluate_critique_operation(
            result, "baseline", critique,
            {"name": "increase-height", "parameters": {"block_id": "box", "plates": 1}}, PALETTE,
        )
        artifact = evaluation.snapshot()
        self.assertFalse(evaluation.success)
        self.assertTrue(artifact["result"]["baseline_preserved"])
        self.assertFalse(artifact["result"]["engineering_validation"]["valid"])
        self.assertTrue(artifact["comparison"]["regression"]["engineering_validity_lost"])
        self.assertIn("NON_INTEGRAL_DIMENSION", " ".join(artifact["result"]["rejection_diagnostics"]))

    def test_malformed_parameters_are_rejected_before_redesign(self):
        result, critique, _ = fixture()
        with self.assertRaisesRegex(CritiqueOperationError, "must be an object"):
            evaluate_critique_operation(result, "baseline", critique, {"name": "recolor", "parameters": None}, PALETTE)


if __name__ == "__main__":
    unittest.main()
