import json
import unittest
from pathlib import Path

from brick_builder.candidate_composition import compose_candidate_set
from brick_builder.local_redesign import Block
from brick_builder.palette import load_palette
from brick_builder.selected_candidate_redesign import SelectedCandidateRedesignSession
from brick_builder.spatial_concept import GenericBoxConcept


ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "brick_builder/palettes/classic-core-v0.json")


def concept(identifier="chosen", width=4, color="#2878b5"):
    return GenericBoxConcept(identifier, identifier, (Block("box", (0, 1, 0), (width, 2, 2), color),),
                             {"camera": "three-quarter", "geometry_refs": ["box"]})


class SelectedCandidateRedesignTests(unittest.TestCase):
    def make_session(self):
        result = compose_candidate_set("make a small box", [concept("chosen"), concept("other", 6)], PALETTE)
        return SelectedCandidateRedesignSession(result, "chosen", PALETTE)

    def test_explicit_selection_retains_provenance_and_round_trips(self):
        session = self.make_session()
        self.assertEqual(session.selected_candidate_id, "chosen")
        self.assertEqual(session.selected_family, "one-box")
        self.assertEqual(session.selected_model_id, "chosen-legoized")
        self.assertTrue(session.candidate_set_hash)
        self.assertEqual(SelectedCandidateRedesignSession.from_serialized(session.serialize()).serialize(), session.serialize())

    def test_accepts_color_only_redesign_and_records_revised_ldr(self):
        session = self.make_session()
        session.set_focus((0, 1, 0), radius=2)
        session.propose("make it red")
        accepted = session.accept()
        self.assertTrue(accepted["success"])
        self.assertIn("assembly", accepted["bridge"])
        self.assertIn("Brick Builder model:", accepted["compiled_ldr"])
        self.assertEqual(session.accepted_concept.boxes[0].color, "#f5a623")

    def test_locked_preservation_and_undo_restore_bridge_state(self):
        session = self.make_session()
        session.set_focus((0, 1, 0), radius=2)
        session.lock_selected()
        session.propose("make it red")
        before = session.serialize()
        self.assertTrue(session.accept()["success"])
        session.undo()
        self.assertEqual(session.blocks[0].color, "#2878b5")
        self.assertEqual(session.locked_ids, {"box"})
        self.assertEqual(session.bridge_evidence["source_concept"]["geometry"][0]["color"], "#2878b5")
        self.assertNotEqual(session.serialize(), before)  # evidence records the accepted/undo operations

    def test_failed_non_integral_proposal_preserves_prior_state_and_proposal(self):
        session = self.make_session()
        session.set_focus((0, 1, 0), radius=2)
        session.propose("make it taller")
        # Force the deterministic bridge rejection while retaining the proposal.
        object.__setattr__(session.redesign.local.proposal, "after", tuple(
            block.moved(size=(block.size[0] + 0.25, block.size[1], block.size[2]))
            for block in session.redesign.local.proposal.after
        ))
        prior = session.accepted_concept.to_dict()
        rejected = session.accept()
        self.assertFalse(rejected["success"])
        self.assertIn("NON_INTEGRAL_DIMENSION", " ".join(rejected["diagnostics"]))
        self.assertEqual(session.accepted_concept.to_dict(), prior)
        self.assertIsNotNone(session.proposal)
        self.assertEqual(json.loads(session.serialize())["bridge_evidence"], session.bridge_evidence)


if __name__ == "__main__":
    unittest.main()
