import os

import pytest

# Force in-memory backend for the whole test session.
os.environ.pop("DATABASE_URL", None)


@pytest.fixture(autouse=True)
def _reset_process_state():
    """Clear module-level caches that would otherwise leak between tests."""
    from services import auth_service
    auth_service._ATTEMPTS.clear()
    yield
    auth_service._ATTEMPTS.clear()


@pytest.fixture()
def memstore():
    """Fresh in-memory persistence store — for db-layer tests that don't need the web app."""
    from db import pool
    pool.reset_memory_store()
    return pool.STATE


@pytest.fixture()
def app():
    from app import create_app
    from db import pool
    pool.reset_memory_store()          # fresh dict store per test
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
