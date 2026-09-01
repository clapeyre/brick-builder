import copy
import json
import unittest

from brick_builder.local_redesign import (
    CAMERA_PRESETS,
    Block,
    LocalRedesignSession,
    make_blocky_boat,
    project_box,
)


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

    def test_three_quarter_projection_has_solid_visible_faces_and_depth_order(self):
        block = Block("wide-box", (0, 0, 0), (8, 2, 4), "#2878b5")
        faces = project_box(block, **dict(zip(("yaw", "pitch"), CAMERA_PRESETS["three-quarter"])))
        names = {face["name"] for face in faces}
        self.assertIn("top", names)
        self.assertGreaterEqual(len(names), 3)
        self.assertEqual(list(faces), sorted(faces, key=lambda face: (face["depth"], face["name"])))
        self.assertTrue(all(len(face["points"]) == 4 for face in faces))
        self.assertTrue(all(face["block_id"] == "wide-box" for face in faces))
        self.assertTrue(all(self._polygon_area(face["points"]) > 0 for face in faces))

    def test_front_projection_uses_the_actual_front_face_dimensions(self):
        block = Block("wide-box", (0, 0, 0), (8, 2, 4), "#2878b5")
        faces = project_box(block, yaw=0, pitch=0, scale=10)
        self.assertEqual([face["name"] for face in faces], ["front"])
        points = faces[0]["points"]
        self.assertEqual(max(x for x, _ in points) - min(x for x, _ in points), 80)
        self.assertEqual(max(y for _, y in points) - min(y for _, y in points), 20)

    def test_named_cameras_are_reproducible_and_distinct(self):
        block = Block("wide-box", (1, 2, 3), (8, 2, 4), "#2878b5")
        projections = {
            name: project_box(block, yaw=yaw, pitch=pitch)
            for name, (yaw, pitch) in CAMERA_PRESETS.items()
        }
        self.assertEqual(projections["front"], project_box(block, yaw=0, pitch=0))
        self.assertEqual(projections["top"], project_box(block, yaw=0, pitch=90))
        signatures = {
            name: tuple((face["name"], face["points"]) for face in faces)
            for name, faces in projections.items()
        }
        self.assertEqual(len(set(signatures.values())), len(CAMERA_PRESETS))

    def test_serialization_round_trip_preserves_stable_box_and_focus_references(self):
        self.session.set_focus((-4, 1.5, 0), radius=2.25, block_id="block-02")
        self.session.toggle_lock("block-04")
        self.session.set_camera("side")
        encoded = self.session.serialize()
        restored = LocalRedesignSession.from_serialized(encoded)
        self.assertEqual(restored.blocks, self.session.blocks)
        self.assertEqual(restored.focus, self.session.focus)
        self.assertEqual(restored.locked_ids, self.session.locked_ids)
        self.assertEqual(restored.snapshot()["camera"], self.session.snapshot()["camera"])
        self.assertEqual(restored.serialize(), encoded)
        self.assertEqual(restored.selected_ids, self.session.selected_ids)

    def test_serialization_rejects_unknown_stable_focus_reference(self):
        value = self.session.snapshot()
        value["focus"]["block_id"] = "missing-box"
        value["format"] = "brick-builder.local-redesign/v1"
        with self.assertRaises(ValueError):
            LocalRedesignSession.from_serialized(value)

    def test_serialization_replays_in_review_edit_references(self):
        self.session.set_focus((0, 0, 0), radius=2.1, block_id="block-01")
        expected = self.session.propose("make this tall")
        restored = LocalRedesignSession.from_serialized(self.session.serialize())
        self.assertIsNotNone(restored.proposal)
        self.assertEqual(restored.proposal.contract, expected.contract)
        self.assertEqual(restored.serialize(), self.session.serialize())

    def test_serialization_rejects_tampered_camera_and_edit_references(self):
        self.session.set_camera("front")
        value = json.loads(self.session.serialize())
        value["camera"]["yaw"] = 12
        with self.assertRaises(ValueError):
            LocalRedesignSession.from_serialized(value)

        self.session.propose("make this tall")
        value = json.loads(self.session.serialize())
        value["proposal"]["changed_ids"] = ["missing-box"]
        with self.assertRaises(ValueError):
            LocalRedesignSession.from_serialized(value)

    @staticmethod
    def _polygon_area(points):
        return abs(
            sum(
                x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
            )
        ) / 2


if __name__ == "__main__":
    unittest.main()
