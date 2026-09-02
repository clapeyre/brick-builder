import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.prompt_evaluation import FORMAT, PromptEvaluationError, evaluate_prompt_evaluation_set


DIMENSIONS = ("identity", "silhouette", "landmarks", "proportions", "symmetry", "accidental_artifacts")


def semantic(prompt, candidate, set_hash, statuses, artifact="a"):
    return {
        "format": "brick-builder.semantic-critique/v1", "prompt_fixture": prompt, "candidate_id": candidate,
        "fixture_hash": f"fixture-{artifact}", "candidate": {"id": candidate, "model_id": "box", "artifact_hashes": {"final": f"final-{artifact}"}},
        "dimensions": {name: {"status": statuses.get(name, "not-assessed"), "expectation": {}, "finding": "declared", "source_evidence": []} for name in DIMENSIONS},
        "engineering_validation": {"status": "success", "valid": True, "structural_valid": True, "diagnostics": []},
        "semantic_resemblance_evaluated": False,
        "traceability": {"candidate_set_hash": set_hash, "visual_critique_format": "brick-builder.visual-critique/v1", "visual_critique_hash": f"visual-{artifact}"},
    }


def operation(prompt, candidate, set_hash, accepted=True):
    return {
        "format": "brick-builder.critique-operation-evaluation/v1", "prompt_fixture": prompt, "candidate_id": candidate, "candidate_set_hash": set_hash,
        "baseline": {"candidate": {"id": candidate, "artifact_hashes": {"final": "final-a"}}, "critique_observations": {}, "engineering_validation": {"valid": True, "structural_valid": True, "status": "success", "diagnostics": []}},
        "operation": {"name": "recolor", "parameters": {"block_id": "box", "color": "red"}}, "proposal": {},
        "result": {"status": "accepted" if accepted else "rejected", "accepted": accepted, "engineering_validation": {"valid": accepted, "structural_valid": accepted, "status": "success" if accepted else "rejected", "diagnostics": []}},
        "comparison": {"improvement": {}, "regression": {}, "semantic_resemblance_evaluated": False},
        "traceability": {"baseline_candidate_set_hash": set_hash, "baseline_evidence_hash": "evidence", "proposal_operation": "recolor", "redesign_format": "brick-builder.selected-candidate-redesign/v1"},
    }


def case(case_id, before, after, op):
    return {"id": case_id, "prompt_fixture": "make a blue box", "candidate_id": "box", "baseline_semantic_critique": before, "revision_semantic_critique": after, "critique_operation_evaluation": op}


class PromptEvaluationTests(unittest.TestCase):
    def test_reports_improvement_and_rejection_separately(self):
        base = semantic("make a blue box", "box", "set-1", {"silhouette": "missing"})
        improved = semantic("make a blue box", "box", "set-1", {"silhouette": "observed"}, artifact="b")
        rejected = semantic("make a blue box", "box", "set-1", {"silhouette": "missing"}, artifact="c")
        result = evaluate_prompt_evaluation_set({"format": FORMAT, "cases": [case("improved", base, improved, operation("make a blue box", "box", "set-1")), case("rejected", base, rejected, operation("make a blue box", "box", "set-1", False))]}).snapshot()
        self.assertEqual(result["summary"]["outcomes"], {"improvement": 1, "regression": 0, "rejection": 1, "unchanged": 0})
        self.assertEqual(result["cases"][0]["semantic_findings"]["silhouette"]["outcome"], "improved")
        self.assertEqual(result["cases"][1]["outcome"], "rejection")
        encoded = json.dumps(result).lower()
        for forbidden in ("rank", "winner", "preference", "score"):
            self.assertNotIn(forbidden, encoded)

    def test_reports_regression_and_preserves_hashes_deterministically(self):
        base = semantic("make a blue box", "box", "set-1", {"identity": "observed"})
        revised = semantic("make a blue box", "box", "set-1", {"identity": "missing"}, artifact="b")
        source = {"format": FORMAT, "cases": [case("regressed", base, revised, operation("make a blue box", "box", "set-1"))]}
        first = evaluate_prompt_evaluation_set(source)
        self.assertEqual(first.snapshot()["cases"][0]["outcome"], "regression")
        self.assertEqual(first.serialize(), evaluate_prompt_evaluation_set(source).serialize())
        with tempfile.TemporaryDirectory() as directory:
            path = first.write(Path(directory) / "evaluation.json")
            self.assertEqual(path.read_text(encoding="utf-8").rstrip("\n"), first.serialize())

    def test_rejects_duplicate_and_provenance_mismatch(self):
        base = semantic("make a blue box", "box", "set-1", {})
        after = semantic("make a blue box", "box", "set-1", {}, artifact="b")
        item = case("same", base, after, operation("make a blue box", "box", "set-1"))
        with self.assertRaisesRegex(PromptEvaluationError, "duplicate id"):
            evaluate_prompt_evaluation_set({"format": FORMAT, "cases": [item, item]})
        broken = dict(item, prompt_fixture="different prompt")
        with self.assertRaisesRegex(PromptEvaluationError, "provenance"):
            evaluate_prompt_evaluation_set({"format": FORMAT, "cases": [broken]})

    def test_rejects_inconsistent_operation_validity_and_provenance(self):
        base = semantic("make a blue box", "box", "set-1", {})
        after = semantic("make a blue box", "box", "set-1", {}, artifact="b")
        item = case("inconsistent", base, after, operation("make a blue box", "box", "set-1"))
        item["critique_operation_evaluation"]["result"]["accepted"] = False
        with self.assertRaisesRegex(PromptEvaluationError, "accepted must match"):
            evaluate_prompt_evaluation_set({"format": FORMAT, "cases": [item]})


if __name__ == "__main__":
    unittest.main()
