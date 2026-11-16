import unittest

from fastapi.testclient import TestClient

from app.main import app


class OperationalReadinessTests(unittest.TestCase):
    def test_liveness_and_security_headers(self):
        with TestClient(app) as client:
            response = client.get("/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("camera=()", response.headers["permissions-policy"])

    def test_untrusted_host_is_rejected(self):
        with TestClient(app) as client:
            response = client.get("/live", headers={"host": "attacker.invalid"})
        self.assertEqual(response.status_code, 400)
