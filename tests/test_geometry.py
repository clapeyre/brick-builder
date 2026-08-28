import json
import unittest
from pathlib import Path

from brick_builder.palette import load_palette
from brick_builder.validation import ValidationError, validate_model
from brick_builder.geometry import profiles_from_palette, transformed_profile

ROOT = Path(__file__).parents[1]
PALETTE = load_palette(ROOT / "config" / "palettes" / "classic-core-v0.json")
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1]


def model(parts):
    return {"schema_version": 1, "model_id": "test", "name": "test", "parts": parts}


def part(pid, name, colour=4, xyz=(0, 0, 0), matrix=None):
    return {"id": pid, "part": name, "colour": colour, "translation_ldu": list(xyz), "matrix": matrix or IDENTITY}


class GeometryTests(unittest.TestCase):
    def test_profile_convention(self):
        profiles = profiles_from_palette(PALETTE)
        brick = profiles["3004.dat"]
        self.assertEqual((brick.x_studs, brick.z_studs), (2, 1))
        self.assertEqual(brick.bounds, (-20, 0, -10, 20, 24, 10))
        self.assertEqual(brick.ports()[0], [(-10, 0, 0), (10, 0, 0)])
        self.assertEqual({p[1] for p in brick.ports()[1]}, {24})
        plate = profiles["3023.dat"]
        self.assertEqual((plate.x_studs, plate.z_studs, plate.height_plates), (2, 1, 1))

    def test_transformed_profile_preserves_rotated_port_coordinates(self):
        profile = profiles_from_palette(PALETTE)["3004.dat"]
        bbox, top, bottom = transformed_profile(profile, part("r", "3004.dat", xyz=(10, -24, 10), matrix=[0, 0, 1, 0, 1, 0, -1, 0, 0]))
        self.assertEqual(bbox, (0, -24, -10, 20, 0, 30))
        self.assertIn((10, -24, 0), top)

    def test_reference_models_are_connected(self):
        for name in ("tiny-red-wall.json", "tiny-blue-step.json"):
            data = json.loads((ROOT / "examples" / "reference_models" / name).read_text())
            validate_model(data, PALETTE)

    def test_floating_and_disconnected_parts_fail(self):
        with self.assertRaises(ValidationError) as caught:
            validate_model(model([part("base", "3005.dat"), part("a", "3005.dat", xyz=(0, -24, 100))]), PALETTE)
        self.assertTrue(any(i.code == "DISCONNECTED_ASSEMBLY" for i in caught.exception.issues))
        with self.assertRaises(ValidationError) as caught:
            validate_model(model([part("a", "3005.dat"), part("b", "3005.dat", xyz=(100, 0, 0))]), PALETTE)
        self.assertTrue(any(i.code == "DISCONNECTED_ASSEMBLY" for i in caught.exception.issues))

    def test_overlap_and_unsupported_contact_fail(self):
        with self.assertRaises(ValidationError) as caught:
            validate_model(model([part("a", "3005.dat"), part("b", "3005.dat", xyz=(0, -4, 0))]), PALETTE)
        self.assertTrue(any(i.code == "GEOMETRY_OVERLAP" for i in caught.exception.issues))
        with self.assertRaises(ValidationError) as caught:
            validate_model(model([part("a", "3005.dat"), part("b", "3005.dat", xyz=(10, -24, 0))]), PALETTE)
        self.assertTrue(any(i.code == "UNSUPPORTED_CONTACT" for i in caught.exception.issues))

    def test_rotation_and_tile_termination(self):
        validate_model(model([part("a", "3004.dat"), part("b", "3004.dat", xyz=(10, -24, 10), matrix=[0, 0, 1, 0, 1, 0, -1, 0, 0])]), PALETTE)
        with self.assertRaises(ValidationError) as caught:
            validate_model(model([part("base", "3005.dat"), part("tile", "3070b.dat", xyz=(0, -8, 0)), part("top", "3005.dat", xyz=(0, -32, 0))]), PALETTE)
        self.assertTrue(any(i.code in {"DISCONNECTED_ASSEMBLY", "UNSUPPORTED_CONTACT"} for i in caught.exception.issues))

    def test_schema_rejects_extra_property(self):
        document = model([part("a", "3005.dat")])
        document["unexpected"] = True
        with self.assertRaises(ValidationError) as caught:
            validate_model(document, PALETTE)
        self.assertTrue(any(i.code == "SCHEMA_INVALID" for i in caught.exception.issues))

    def test_schema_rejects_invalid_model_id_pattern(self):
        document = model([part("a", "3005.dat")])
        document["model_id"] = "Not Valid"
        with self.assertRaises(ValidationError) as caught:
            validate_model(document, PALETTE)
        self.assertTrue(any(i.code == "SCHEMA_INVALID" for i in caught.exception.issues))
