"""P0 — production must fail loudly, never silently degrade."""
import pytest

from config import Config, _DEV_JWT_SECRET, _DEV_SECRET_KEY

_GOOD_SK = "s" * 40
_GOOD_JWT = "j" * 40
_GOOD_DB = "postgresql://localhost:5432/unifix"


def _prod(monkeypatch, **over):
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", over.get("sk", _GOOD_SK))
    monkeypatch.setattr(Config, "JWT_SECRET", over.get("jwt", _GOOD_JWT))
    monkeypatch.setattr(Config, "DATABASE_URL", over.get("db", _GOOD_DB))


# ── secrets ────────────────────────────────────────────────────────────────

def test_prod_missing_secret_key_aborts(monkeypatch):
    _prod(monkeypatch, sk="")
    with pytest.raises(RuntimeError):
        Config.validate()


def test_prod_default_secret_key_aborts(monkeypatch):
    _prod(monkeypatch, sk=_DEV_SECRET_KEY)
    with pytest.raises(RuntimeError):
        Config.validate()


def test_prod_default_jwt_secret_aborts(monkeypatch):
    _prod(monkeypatch, jwt=_DEV_JWT_SECRET)
    with pytest.raises(RuntimeError):
        Config.validate()


def test_prod_short_secret_aborts(monkeypatch):
    _prod(monkeypatch, sk="tooshort")
    with pytest.raises(RuntimeError):
        Config.validate()


def test_prod_missing_database_url_aborts(monkeypatch):
    _prod(monkeypatch, db="")
    with pytest.raises(RuntimeError):
        Config.validate()


def test_prod_valid_config_passes(monkeypatch):
    _prod(monkeypatch)
    Config.validate()  # must not raise


def test_dev_unsafe_config_only_warns(monkeypatch):
    monkeypatch.setattr(Config, "APP_ENV", "development")
    monkeypatch.setattr(Config, "SECRET_KEY", "")
    monkeypatch.setattr(Config, "JWT_SECRET", "")
    Config.validate()  # must not raise in dev


# ── database backend selection ─────────────────────────────────────────────

def test_prod_no_backend_raises_not_memory(monkeypatch):
    from db import pool
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(pool, "_try_postgres", lambda: False)
    monkeypatch.setattr(pool, "_try_firestore", lambda: False)
    with pytest.raises(RuntimeError):
        pool.init_db()


def test_dev_no_backend_falls_to_memory(monkeypatch):
    from db import pool
    monkeypatch.setattr(Config, "APP_ENV", "development")
    monkeypatch.setattr(pool, "_try_postgres", lambda: False)
    monkeypatch.setattr(pool, "_try_firestore", lambda: False)
    pool.init_db()
    assert pool.STATE["mode"] == "memory"


def test_prod_uses_firestore_when_postgres_down(monkeypatch):
    from db import pool
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(pool, "_try_postgres", lambda: False)

    def _fake_fs():
        pool.STATE["mode"] = "firestore"
        return True

    monkeypatch.setattr(pool, "_try_firestore", _fake_fs)
    pool.init_db()
    assert pool.STATE["mode"] == "firestore"


# ── cookies ────────────────────────────────────────────────────────────────

def test_prod_cookies_secure(monkeypatch):
    from blueprints.auth import _secure_cookies
    monkeypatch.setattr(Config, "APP_ENV", "production")
    assert _secure_cookies() is True


def test_dev_cookies_not_secure(monkeypatch):
    from blueprints.auth import _secure_cookies
    monkeypatch.setattr(Config, "APP_ENV", "development")
    assert _secure_cookies() is False


# ── demo seeding / default admin ──────────────────────────────────────────

def test_prod_no_demo_faculty_or_notices(monkeypatch, memstore):
    from db import seeds, users, notices
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "INITIAL_ADMIN_USERNAME", "sir")
    monkeypatch.setattr(Config, "INITIAL_ADMIN_PIN", "246810")
    seeds.run()
    assert users.get_by_username("prof.rao") is None
    assert users.get_by_username("admin") is None
    assert notices.list_all() == []
    # the configured admin exists and is forced to change its PIN
    sir = users.get_by_username("sir")
    assert sir and sir["role"] == "admin" and sir["must_change_pin"] is True


def test_prod_no_admin_config_aborts(monkeypatch, memstore):
    from db import seeds
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "INITIAL_ADMIN_USERNAME", "")
    monkeypatch.setattr(Config, "INITIAL_ADMIN_PIN", "")
    with pytest.raises(RuntimeError):
        seeds.run()


def test_prod_demo_override_allows_seeding(monkeypatch, memstore):
    from db import seeds, users
    monkeypatch.setattr(Config, "APP_ENV", "production")
    monkeypatch.setattr(Config, "INITIAL_ADMIN_USERNAME", "sir")
    monkeypatch.setattr(Config, "INITIAL_ADMIN_PIN", "246810")
    monkeypatch.setattr(Config, "ALLOW_PROD_DEMO_SEED", True)
    seeds.run()
    assert users.get_by_username("prof.rao") is not None


def test_dev_still_seeds_admin_0000(monkeypatch, memstore):
    from db import seeds, users
    from services.auth_service import verify_pin
    seeds.run()
    admin = users.get_by_username("admin")
    assert admin and verify_pin("0000", admin["pin_hash"])
