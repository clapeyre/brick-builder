import json
import tempfile
import unittest
from pathlib import Path

from brick_builder.child_controller import ChildController
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.spatial_concept import GenericBoxConcept


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier: str, width: int = 2) -> GenericBoxConcept:
    return GenericBoxConcept(identifier, f"A {identifier}", (Block("box", (0, 1, 0), (width, 2, 2), "#2878b5"),), {"camera": "three-quarter", "geometry_refs": ["box"]})


class ChildControllerTests(unittest.TestCase):
    def make_controller(self, directory: str) -> ChildController:
        return ChildController(directory, PALETTE)

    def test_generation_exposes_ordered_cards_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.make_controller(directory)
            before = controller.snapshot()
            self.assertFalse(before["selection_enabled"])
            result = controller.create_candidate_set("make two little towers", [concept("first"), concept("second", 4)])
            self.assertTrue(result["generated"])
            self.assertEqual([card["id"] for card in result["candidate_cards"]], ["first", "second"])
            self.assertTrue((Path(result["generation_run"]) / "visual-critique.json").is_file())
            self.assertNotIn("rank", json.dumps(result))

    def test_selection_is_disabled_before_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "successful candidate set"):
                self.make_controller(directory).select("first")

    def test_explicit_selection_retains_receipt_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.make_controller(directory)
            controller.generate("request", [concept("first"), concept("second")])
            receipt = controller.select("second")
            state = controller.snapshot()
            self.assertEqual(receipt["selected_candidate_id"], "second")
            self.assertEqual(state["selection_receipt"]["candidate_set_hash"], state["candidate_set_hash"])
            self.assertTrue(state["selection_receipt_hash"])

    def test_proposal_rejection_accept_and_undo_are_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.make_controller(directory)
            controller.generate("request", [concept("first"), concept("second")])
            controller.select("first")
            controller.focus((0, 1, 0), radius=2)
            controller.propose("make it red")
            self.assertEqual(controller.snapshot()["proposal_status"], "proposed")
            accepted = controller.accept()
            self.assertTrue(accepted["success"])
            self.assertEqual(controller.snapshot()["proposal_status"], "accepted")
            controller.undo()
            self.assertEqual(controller.snapshot()["proposal_status"], "undone")

    def test_bridge_rejection_is_visible_and_keeps_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.make_controller(directory)
            controller.generate("request", [concept("first"), concept("second")])
            controller.select("first")
            controller.focus((0, 1, 0), radius=2)
            controller.propose("make it taller")
            proposal = controller.session.redesign.local.proposal  # type: ignore[union-attr]
            object.__setattr__(proposal, "after", tuple(
                block.moved(size=(block.size[0] + 0.25, block.size[1], block.size[2]))
                for block in proposal.after
            ))
            rejected = controller.accept()
            self.assertFalse(rejected["success"])
            self.assertEqual(controller.snapshot()["proposal_status"], "rejected")
            self.assertIsNotNone(controller.snapshot()["proposal"])
            self.assertIn("NON_INTEGRAL_DIMENSION", " ".join(rejected["diagnostics"]))

    def test_restart_preserves_source_evidence_and_clears_active_state(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.make_controller(directory)
            generated = controller.generate("request", [concept("first"), concept("second")])
            run = Path(generated["generation_run"])
            controller.select("first")
            controller.restart()
            state = controller.snapshot()
            self.assertTrue(state["generated"])
            self.assertIsNone(state["selected_candidate_id"])
            self.assertEqual(state["candidate_cards"][0]["id"], "first")
            self.assertTrue((run / "candidate-set.json").is_file())
            self.assertTrue((run / "candidates/first/final.ldr").is_file())

    def test_repeated_generation_is_deterministic_beyond_fresh_directory_name(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.make_controller(directory).generate("request", [concept("first"), concept("second", 4)])
            second = self.make_controller(directory).generate("request", [concept("first"), concept("second", 4)])
            first_set = json.loads((Path(first["generation_run"]) / "candidate-set.json").read_text())
            second_set = json.loads((Path(second["generation_run"]) / "candidate-set.json").read_text())
            self.assertEqual(first_set, second_set)
            self.assertEqual(first["candidate_set_hash"], second["candidate_set_hash"])


if __name__ == "__main__":
    unittest.main()
