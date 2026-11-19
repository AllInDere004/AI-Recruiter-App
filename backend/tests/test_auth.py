"""Authentication regression checks using isolated, in-memory databases."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
import jwt
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.config import settings
from app.database import Base, get_db
from app.models.user import User
from app.services.auth_service import create_access_token, get_password_hash, verify_password


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.engine_patch.start()

        def test_db():
            with Session(self.engine) as session:
                yield session

        self.original_overrides = main.app.dependency_overrides.copy()
        main.app.dependency_overrides[get_db] = test_db
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(self.original_overrides)
        self.engine_patch.stop()
        self.engine.dispose()

    def register(self, email="person@example.com", password="test-password"):
        return self.client.post("/api/auth/register", json={"email": email, "password": password})

    def login(self, email="person@example.com", password="test-password"):
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def bearer(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_registration_hashes_password_and_filters_response(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json()), {"id", "email", "is_active", "created_at"})
        self.assertTrue(response.json()["is_active"])
        with Session(self.engine) as db:
            user = db.query(User).one()
            self.assertNotEqual(user.hashed_password, "test-password")
            self.assertTrue(verify_password("test-password", user.hashed_password))

    def test_duplicate_email_is_rejected_case_insensitively(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register(email="PERSON@example.com").status_code, 400)
        with Session(self.engine) as db:
            self.assertEqual(db.query(User).count(), 1)

    def test_login_and_current_user(self):
        registered = self.register().json()
        response = self.login(email="PERSON@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token_type"], "bearer")
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        self.assertEqual(payload["sub"], registered["email"])
        self.assertGreater(payload["exp"], datetime.now(timezone.utc).timestamp())
        me = self.client.get("/api/auth/me", headers=self.bearer(token))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json(), registered)

    def test_incorrect_password_and_unknown_email(self):
        self.register()
        for email, password in [("person@example.com", "incorrect"), ("unknown@example.com", "test-password")]:
            with self.subTest(email=email):
                response = self.login(email, password)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assertEqual(response.json()["detail"], "Incorrect email or password")

    def test_missing_and_malformed_tokens(self):
        for headers in [{}, self.bearer("not-a-jwt"), {"Authorization": "Basic invalid"}]:
            response = self.client.get("/api/auth/me", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_expired_tampered_and_incomplete_tokens(self):
        self.register()
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        tokens = [
            create_access_token({"sub": "person@example.com"}, timedelta(seconds=-5)),
            jwt.encode({"sub": "person@example.com", "exp": future}, "wrong-signing-key-" + "x" * 64, algorithm="HS256"),
            jwt.encode({"sub": "person@example.com", "exp": future}, settings.JWT_SECRET_KEY, algorithm="HS384"),
            jwt.encode({"sub": "person@example.com"}, settings.JWT_SECRET_KEY, algorithm="HS256"),
            create_access_token({}),
            create_access_token({"sub": 123}),
            create_access_token({"sub": ""}),
        ]
        for token in tokens:
            with self.subTest(token_kind=tokens.index(token)):
                self.assertEqual(self.client.get("/api/auth/me", headers=self.bearer(token)).status_code, 401)

    def test_inactive_user_cannot_login_or_use_existing_token(self):
        self.register()
        token = self.login().json()["access_token"]
        with Session(self.engine) as db:
            db.query(User).one().is_active = False
            db.commit()
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.bearer(token)).status_code, 401)

    def test_deleted_user_token_is_rejected(self):
        self.register()
        token = self.login().json()["access_token"]
        with Session(self.engine) as db:
            db.execute(delete(User))
            db.commit()
        self.assertEqual(self.client.get("/api/auth/me", headers=self.bearer(token)).status_code, 401)

    def test_invalid_email_and_password_boundaries(self):
        self.assertEqual(self.register(email="invalid-email").status_code, 422)
        for password in ["", "x" * 73, "\u00e9" * 37, "null\x00character"]:
            with self.subTest(length=len(password)):
                self.assertEqual(self.register(password=password).status_code, 422)
        self.assertEqual(self.register(password="x" * 72).status_code, 201)
        self.assertEqual(self.login(password="x" * 72).status_code, 200)

    def test_token_expiration_and_password_helpers(self):
        data = {"sub": "person@example.com"}
        token = create_access_token(data, timedelta(minutes=5))
        self.assertEqual(data, {"sub": "person@example.com"})
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        self.assertAlmostEqual(payload["exp"] - datetime.now(timezone.utc).timestamp(), 300, delta=2)
        hashed = get_password_hash("correct-password")
        self.assertTrue(verify_password("correct-password", hashed))
        self.assertFalse(verify_password("incorrect-password", hashed))
        self.assertFalse(verify_password("correct-password", "invalid-hash"))
        self.assertFalse(verify_password("x" * 73, hashed))

    def test_existing_routes_and_both_frontend_cors_origins(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/health").status_code, 200)
        for origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
            response = self.client.options("/api/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], origin)


if __name__ == "__main__":
    unittest.main()
