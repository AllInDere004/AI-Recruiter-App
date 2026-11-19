import pytest

from app.config import settings


@pytest.fixture(scope="session", autouse=True)
def isolated_jwt_secret():
    """Tests must never sign fixtures with a developer's configured secret."""
    previous = settings.JWT_SECRET_KEY
    settings.JWT_SECRET_KEY = "synthetic-test-signing-key-" + ("x" * 64)
    try:
        yield
    finally:
        settings.JWT_SECRET_KEY = previous
