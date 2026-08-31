import copy
import unittest

from brick_builder.local_redesign import LocalRedesignSession, make_blocky_boat


class LocalRedesignSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = LocalRedesignSession()

    def test_boat_is_generic_box_blockout_with_stable_ids(self):
        blocks = make_blocky_boat()
        self.assertGreaterEqual(len(blocks), 6)
        self.assertEqual(len({block.id for block in blocks}), len(blocks))
        self.assertTrue(all(len(block.size) == 3 for block in blocks))

    def test_focus_radius_selects_spatial_blocks_and_rotation_is_preserved(self):
        self.session.set_focus((0, 0, 0), radius=1.5)
        self.assertEqual(self.session.selected_ids, ("block-01",))
        before = self.session.yaw, self.session.pitch
        self.session.rotate(25, -5)
        self.assertNotEqual((self.session.yaw, self.session.pitch), before)
        self.assertEqual(self.session.selected_ids, ("block-01",))

    def test_contract_identifies_changed_protected_and_spillover_geometry(self):
        self.session.set_focus((0, 0, 0), radius=2.1)
        proposal = self.session.propose("make this friendlier")
        self.assertTrue(proposal.changed_ids)
        self.assertIn("block-01", proposal.selected_ids)
        self.assertTrue(set(proposal.protected_ids).isdisjoint(proposal.changed_ids))
        self.assertTrue(set(proposal.spillover_ids) <= set(proposal.changed_ids))
        contract = proposal.contract
        self.assertEqual(contract["instruction"], "make this friendlier")
        self.assertEqual(contract["changed_ids"], list(proposal.changed_ids))
        self.assertEqual(contract["spillover_ids"], list(proposal.spillover_ids))
        self.assertEqual(len(contract["before"]), len(proposal.changed_ids))
        self.assertEqual(len(contract["after"]), len(proposal.changed_ids))
        self.assertEqual(contract["invariants"][0], "protected blocks remain identical")
        before_by_id = {block.id: block for block in proposal.before}
        after_by_id = {block.id: block for block in proposal.after}
        actual_changes = {
            block_id
            for block_id in before_by_id
            if before_by_id[block_id] != after_by_id[block_id]
        }
        self.assertEqual(actual_changes, set(proposal.changed_ids))
        self.assertTrue(
            all(
                self.session._distance(before_by_id[block_id].center, self.session.focus.point)
                > self.session.focus.radius
                for block_id in proposal.spillover_ids
            )
        )

    def test_locked_blocks_are_hard_constraints(self):
        original = copy.deepcopy(self.session.blocks)
        self.session.set_focus((0, 0, 0), radius=3)
        self.session.lock_selected()
        proposal = self.session.propose("make this tall")
        self.assertTrue(set(self.session.locked_ids).isdisjoint(proposal.changed_ids))
        after_by_id = {block.id: block for block in proposal.after}
        before_by_id = {block.id: block for block in original}
        for block_id in self.session.locked_ids:
            self.assertEqual(after_by_id[block_id], before_by_id[block_id])

    def test_retry_preserves_focus_and_locks_but_produces_new_proposal(self):
        self.session.set_focus((0, 0, 0), radius=3)
        self.session.toggle_lock("block-02")
        focus = self.session.focus
        locks = set(self.session.locked_ids)
        first = self.session.propose("make this tall")
        second = self.session.retry()
        self.assertEqual(self.session.focus, focus)
        self.assertEqual(self.session.locked_ids, locks)
        self.assertEqual(first.selected_ids, second.selected_ids)
        self.assertEqual(first.locked_ids, second.locked_ids)
        self.assertNotEqual(first.after, second.after)

    def test_changing_focus_or_locks_starts_a_fresh_proposal_sequence(self):
        self.session.set_focus((0, 0, 0), radius=3)
        self.session.propose("make this tall")
        self.assertEqual(self.session.retry().retry_number, 1)
        self.session.set_radius(2)
        self.assertEqual(self.session.propose("make this tall").retry_number, 0)
        self.session.retry()
        self.session.toggle_lock("block-01")
        self.assertEqual(self.session.propose("make this tall").retry_number, 0)

    def test_accept_then_undo_restores_exact_state(self):
        original = copy.deepcopy(self.session.snapshot())
        self.session.set_focus((0, 0, 0), radius=3)
        self.session.toggle_lock("block-02")
        before_accept = copy.deepcopy(self.session.snapshot())
        self.session.propose("make this wide")
        self.session.accept()
        self.assertNotEqual(self.session.snapshot()["blocks"], before_accept["blocks"])
        self.session.undo()
        restored = self.session.snapshot()
        self.assertEqual(restored["blocks"], before_accept["blocks"])
        self.assertEqual(restored["focus"], before_accept["focus"])
        self.assertEqual(restored["locked_ids"], before_accept["locked_ids"])
        self.assertEqual(restored["camera"], before_accept["camera"])
        self.assertIsNone(restored["proposal"])
        with self.assertRaises(ValueError):
            self.session.undo()
        self.assertNotEqual(restored, original)

    def test_proposal_requires_focus_and_instruction(self):
        session = LocalRedesignSession([make_blocky_boat()[0]])
        session.set_focus((100, 100, 100), radius=1)
        with self.assertRaises(ValueError):
            session.propose("make it nice")
        session.set_focus((0, 0, 0), radius=1)
        with self.assertRaises(ValueError):
            session.propose(" ")


if __name__ == "__main__":
    unittest.main()
