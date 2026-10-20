"""Smoke tests: no auth, no database, no accidental public writes."""
import unittest
from fastapi.testclient import TestClient
from backend.api.main import app

class AccessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_public_metadata_only(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["api_version"], "0.4.0")

    def test_protected_routes_fail_closed_without_database(self):
        self.assertEqual(self.client.get("/storage").status_code, 503)
        self.assertEqual(self.client.post("/storage", json={
            "contract_number": "DEMO-1", "owner_name": "Test", "vin": "TEST123", "brand_model": "Test"
        }).status_code, 503)

    def test_no_public_account_registration(self):
        self.assertEqual(self.client.post("/auth/register", json={}).status_code, 404)

    def test_photo_endpoint_is_not_public(self):
        self.assertEqual(self.client.post("/storage/00000000-0000-0000-0000-000000000000/photos", json={}).status_code, 503)

    def test_handover_requires_backend(self):
        ident = "00000000-0000-0000-0000-000000000000"
        self.assertEqual(self.client.post(f"/storage/{ident}/request-return",
            json={"version": 1, "note": "demo"}).status_code, 503)
        self.assertEqual(self.client.post(f"/storage/{ident}/handover",
            json={"version": 1, "received_by": "Demo Client",
                  "condition_at_return": "Inspected at handover",
                  "all_keys_returned": True, "documents_returned": True}).status_code, 503)

    def test_photo_upload_requires_database(self):
        contract_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            f"/storage/{contract_id}/photos",
            data={"kind": "front", "note": "Test"},
            files={"photo": ("test.jpg", b"not-a-photo", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 503)

    def test_acceptance_requires_database(self):
        contract_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            f"/storage/{contract_id}/accept",
            json={"version": 1, "condition_confirmed": True},
        )
        self.assertEqual(response.status_code, 503)

if __name__ == "__main__":
    unittest.main()
