import json
import pytest

from brick_builder.concept_redesign import ConceptRedesignSession
from brick_builder.spatial_concept import SpatialConceptSession


def accepted():
    spatial = SpatialConceptSession("make a tiny blue lookout")
    boxes = [
        {"ref": "base", "center": [0, 0, 0], "size": [4, 1, 4], "color": "#2878b5"},
        {"ref": "tower", "center": [0, 2, 0], "size": [2, 3, 2], "color": "#f5a623"},
    ]
    response = {"kind": "concepts", "concepts": [
        {"id": "lookout-a", "label": "A", "geometry": boxes,
         "render": {"camera": "three-quarter", "geometry_refs": ["base", "tower"]}},
        {"id": "lookout-b", "label": "B", "geometry": boxes,
         "render": {"camera": "front", "geometry_refs": ["base", "tower"]}},
    ]}
    spatial.submit(response)
    return spatial, "lookout-a"


class TestConceptRedesign:
    def test_accepted_concept_round_trip_preserves_boxes_and_camera(self):
        spatial, concept_id = accepted()
        session = ConceptRedesignSession.from_spatial_session(spatial, concept_id)
        encoded = session.serialize()
        restored = ConceptRedesignSession.from_serialized(encoded)
        assert restored.serialize() == encoded
        assert restored.blocks == session.blocks
        assert restored.starting_concept.render == session.starting_concept.render

    def test_locked_box_is_preserved_and_evidence_records_instruction_and_spillover(self):
        spatial, concept_id = accepted()
        session = ConceptRedesignSession.from_spatial_session(spatial, concept_id)
        session.set_focus((0, 0, 0), radius=3, block_id="base")
        session.lock_selected()
        proposal = session.propose("make the tower taller")
        assert "base" not in proposal["changed_ids"]
        assert session.evidence[-1]["proposal"]["instruction"] == "make the tower taller"
        assert "spillover_ids" in proposal

    def test_retry_preserves_focus_locks_and_undo_restores_start(self):
        spatial, concept_id = accepted()
        session = ConceptRedesignSession.from_spatial_session(spatial, concept_id)
        session.set_focus((0, 0, 0), radius=3)
        session.toggle_lock("base")
        start = json.loads(session.serialize())
        first = session.propose("make this taller")
        second = session.retry()
        assert first["selection"] == second["selection"]
        assert first["locked"] == second["locked"]
        session.accept()
        session.undo()
        assert session.blocks == session.starting_concept.boxes
        assert session.focus.block_id == None
        assert session.locked_ids == {"base"}
        assert json.loads(session.serialize())["starting_concept"] == start["starting_concept"]
        assert [item["operation"] for item in session.evidence] == ["propose", "retry", "accept", "undo"]
