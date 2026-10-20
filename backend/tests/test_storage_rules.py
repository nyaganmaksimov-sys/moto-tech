import unittest
from backend.api.storage_rules import normalize_vin, photo_validation_errors, validate_transition

class StorageRulesTests(unittest.TestCase):
    def setUp(self):
        self.photos = [{"kind": kind, "note": ""} for kind in ("front", "rear", "left", "right", "vin")]

    def test_normalization_supports_frame_numbers(self):
        self.assertEqual(normalize_vin(" abc-123 "), "ABC123")

    def test_requires_all_views(self):
        self.assertEqual(photo_validation_errors(self.photos), [])
        self.assertIn("vin", photo_validation_errors(self.photos[:-1])[0])

    def test_damage_note_required(self):
        self.assertTrue(photo_validation_errors(self.photos + [{"kind": "damage", "note": ""}]))

    def test_cannot_skip_requested_return(self):
        with self.assertRaises(ValueError):
            validate_transition("stored", "returned", self.photos)

    def test_cannot_accept_without_photos(self):
        with self.assertRaises(ValueError):
            validate_transition("draft", "stored", [])

    def test_accepts_complete_inspection(self):
        validate_transition("draft", "stored", self.photos)

if __name__ == "__main__":
    unittest.main()
