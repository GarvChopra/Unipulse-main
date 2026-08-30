# UniPulse — Phase 0 + A (Restructure & Data Foundations) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase-1 fork in `unipulse-campus/` into a clean Flask-app-factory
project with the campus data model, RBAC, and seed data — a skeleton that boots
(Postgres or in-memory) with working auth and nothing else wired.

**Architecture:** Flask app factory + blueprints. `db/` owns all persistence (Postgres
primary via `DATABASE_URL`, in-memory dict store otherwise — same shapes both ways).
`domain/` is pure Python (constants, dataclasses, RBAC) with zero infra imports.
`services/` depends on `db/` + `domain/`. Server-rendered Jinja, no build step.

**Tech Stack:** Python 3.12, Flask 3, psycopg 3 + psycopg-pool, PyJWT, bcrypt, pytest 9.
Groq / Resend / ImageKit are later phases — not touched here.

**Spec:** `docs/superpowers/specs/2026-08-30-unipulse-campus-design.md` (read §3, §4, §5, §6, §7 before starting).

## Global Constraints

- Product name **UniPulse**; institution **GL Bajaj Institute of Technology and Management** (short: **GL Bajaj**). Grievance code prefix **`GLB-CAMP-`**, zero-padded to 5 digits (`GLB-CAMP-00001`).
- Roles are exactly `reporter` and `admin` (string values). RBAC is a role→permission map; never hard-code role checks in routes except the two blueprint `before_request` guards.
- Categories (exact, ordered): `Electric, Plumbing, Civil, Mechanical, Power, IT / Network`.
- Statuses (exact, ordered): `reported, verified, assigned, in_progress, resolved, admin_verified, closed`. Forward-only + one logged `reopen` (`resolved|admin_verified → in_progress`).
- Responsible Units: College → `Infrastructure, Sanitation, Housekeeping, Landscaping, Mess, Parking`; Academics → `Class, Lab`.
- Location types: `academics_block, hostels, mess_canteen, playground, outer_area` (+ `block, floor` rows for the Academics drill-down). Outer Area sub-zones: `Common/Electrical, Security, Lawn Area, Sewage, Drainage`.
- `RECURRING_WINDOW_DAYS = 14`. `GAP_THRESHOLD = 4`.
- Timestamps are epoch floats (`time.time()`), never `datetime`.
- No `session`, no Firebase, no OAuth. Auth = JWT in httpOnly `SameSite=Strict` cookies.
- Every module under `domain/` imports only stdlib + other `domain/` modules.
- Tests run against the in-memory backend with no `DATABASE_URL` set.
- Commits: `git add` **only** paths under `unipulse-campus/`. Ask the user before the first commit (the git repo root is the user's home directory).

---

## File Structure

**Created:**
- `config.py` — env config object
- `app.py` — **replaced**: app factory `create_app()`, blueprint registration, `init_db()` + seeds on startup
- `wsgi.py` — `from app import create_app; app = create_app()`
- `db/__init__.py`, `db/pool.py`, `db/schema.py`, `db/users.py`, `db/locations.py`, `db/grievances.py`, `db/evidence.py`, `db/timeline.py`, `db/recurring.py`, `db/notices.py`, `db/audit.py`
- `domain/rbac.py`
- `blueprints/__init__.py`, `blueprints/auth/__init__.py`
- `templates/base_faculty.html` (stub), `templates/base_admin.html` (stub)
- `static/css/app.css` (stub)
- `tests/__init__.py`, `tests/conftest.py`, `tests/test_constants.py`, `tests/test_rbac.py`, `tests/test_code_generator.py`, `tests/test_recurring_key.py`, `tests/test_seeds.py`, `tests/test_auth.py`, `tests/test_boot.py`
- `pytest.ini`

**Rewritten in place:**
- `domain/constants.py` — campus constants (full replace)
- `domain/models.py` — campus dataclasses (full replace)
- `services/auth_service.py` — DB-backed login, drop the account-dict params
- `templates/login.html` — point form at the auth blueprint
- `requirements.txt` — drop unused deps

**Deleted:**
- `database.py` (logic moves to `db/`), `ai_engine.py`, `classifier.py`, `email_sender.py`
- `repositories/` (whole dir)
- `services/ai_service.py`, `services/ban_service.py`, `services/cache_service.py`, `services/issue_service.py`, `services/notification_service.py`, `services/rate_limit_service.py`, `services/sla_service.py`
- `templates/index.html`, `templates/issues.html`, `templates/my_issues.html`, `templates/community.html`, `templates/stats.html`, `templates/complaint_print.html`
- `static/js/issues-store.js`
- `models/spam_clf.pkl`, `models/` dir
- `Procfile` old content → rewrite; `nixpacks.toml` keep
- `PHASE1_NOTES.md` stays (historical)

---

## Phase 0 — Restructure & Strip

### Task 1: Prune to the keeper set

**Files:**
- Delete: `database.py`, `ai_engine.py`, `classifier.py`, `email_sender.py`, `repositories/` (dir), `services/ai_service.py`, `services/ban_service.py`, `services/cache_service.py`, `services/issue_service.py`, `services/notification_service.py`, `services/rate_limit_service.py`, `services/sla_service.py`, `templates/index.html`, `templates/issues.html`, `templates/my_issues.html`, `templates/community.html`, `templates/stats.html`, `templates/complaint_print.html`, `static/js/issues-store.js`, `models/` (dir)
- Modify: `requirements.txt`

**Interfaces:**
- Produces: a repo containing only `app.py` (old, about to be replaced), `domain/`, `services/{auth_service,storage_service,validation_service}.py`, `templates/{base.html,login.html}`, `static/`, `PHASE1_NOTES.md`, `docs/`.

- [ ] **Step 1: Delete the out-of-scope modules**

```bash
cd "C:/Users/rocky/OneDrive/Desktop/unipulse/unipulse-campus"
rm -f database.py ai_engine.py classifier.py email_sender.py
rm -rf repositories models
rm -f services/ai_service.py services/ban_service.py services/cache_service.py \
      services/issue_service.py services/notification_service.py \
      services/rate_limit_service.py services/sla_service.py
rm -f templates/index.html templates/issues.html templates/my_issues.html \
      templates/community.html templates/stats.html templates/complaint_print.html
rm -f static/js/issues-store.js
```

- [ ] **Step 2: Trim `requirements.txt`** to exactly:

```
flask==3.0.0
python-dotenv==1.0.0
gunicorn==21.2.0
psycopg[binary]==3.2.10
psycopg-pool==3.2.8
PyJWT==2.8.0
bcrypt==4.1.3
requests==2.32.3
pytest==9.0.3
```

- [ ] **Step 3: Verify the tree**

Run: `find . -name '*.py' -not -path './__pycache__/*' -not -path './docs/*' | sort`
Expected: `app.py`, `domain/__init__.py`, `domain/constants.py`, `domain/models.py`, `services/__init__.py`, `services/auth_service.py`, `services/storage_service.py`, `services/validation_service.py` (plus any `__pycache__` you can ignore).

- [ ] **Step 4: Commit** (ask the user first — see Global Constraints)

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus"
git commit -m "chore(unipulse): prune reference modules out of campus scope"
```

---

### Task 2: `config.py` + `pytest.ini` + test scaffold

**Files:**
- Create: `config.py`, `pytest.ini`, `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_boot.py` (created here, filled in Task 6)

**Interfaces:**
- Produces: `config.Config` with attributes `DATABASE_URL, SECRET_KEY, JWT_SECRET, APP_ENV, GROQ_API_KEY, RESEND_API_KEY, IMAGEKIT_PRIVATE_KEY` (all `str`, empty default); `config.Config.is_production() -> bool`.
- Produces: pytest fixture `client` (Flask test client, in-memory DB, fresh store per test) and `app` (the `Flask` object).

- [ ] **Step 1: Write `config.py`**

```python
"""Environment configuration. One object, read once at startup."""
import os


class Config:
    DATABASE_URL         = os.environ.get("DATABASE_URL", "").strip()
    SECRET_KEY           = os.environ.get("SECRET_KEY", "").strip() or "unipulse-dev-secret"
    JWT_SECRET           = os.environ.get("JWT_SECRET", "").strip() or "unipulse-jwt-dev-secret"
    APP_ENV              = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).lower()
    GROQ_API_KEY         = os.environ.get("GROQ_API_KEY", "").strip()
    RESEND_API_KEY       = os.environ.get("RESEND_API_KEY", "").strip()
    IMAGEKIT_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY", "").strip()

    @classmethod
    def is_production(cls) -> bool:
        return cls.APP_ENV == "production"
```

- [ ] **Step 2: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
addopts = -q
filterwarnings =
    ignore::DeprecationWarning
```

- [ ] **Step 3: Write `tests/__init__.py`** (empty file)

- [ ] **Step 4: Write `tests/conftest.py`**

```python
import os
import pytest

# Force in-memory backend for the whole test session.
os.environ.pop("DATABASE_URL", None)


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
```

- [ ] **Step 5: Create empty `tests/test_boot.py`** with a placeholder that skips:

```python
import pytest

@pytest.mark.skip(reason="filled in Task 6")
def test_placeholder():
    pass
```

- [ ] **Step 6: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/config.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/pytest.ini" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests"
git commit -m "chore(unipulse): config + pytest scaffold"
```

---

### Task 3: `db/pool.py` — connection pool + in-memory store

**Files:**
- Create: `db/__init__.py`, `db/pool.py`
- Test: `tests/test_boot.py` (extended in Task 6)

**Interfaces:**
- Produces:
  - `pool.STATE` — dict: `{"mode": "memory"|"postgres", "pg_pool": <ConnectionPool|None>, "mem": {<table>: [<dict>, ...], ...}, "seq": {<name>: int}}`
  - `pool.init_db() -> None` — picks Postgres if `Config.DATABASE_URL` and psycopg import OK (with the reference's 3-attempt retry), else `mode="memory"`. Calls `schema.ensure(conn)` on the Postgres path; inits empty `mem` tables on the memory path.
  - `pool.reset_memory_store() -> None` — clears `STATE["mem"]` and `STATE["seq"]`, sets `mode="memory"`. For tests.
  - `pool.connection()` — context manager yielding a psycopg connection (Postgres mode only; raises `RuntimeError` in memory mode — memory callers never use it).
  - `pool.next_seq(name: str) -> int` — atomic-ish integer sequence. Postgres: `nextval`. Memory: `STATE["seq"][name] += 1`.
  - `pool.is_memory() -> bool`

- [ ] **Step 1: Write `db/__init__.py`**

```python
from db import pool  # noqa: F401
```

- [ ] **Step 2: Write `db/pool.py`**

Extract from the deleted `database.py` (git history: `git show HEAD~2:OneDrive/Desktop/unipulse/unipulse-campus/database.py`) the `ConnectionPool` setup block (the `init_db` Postgres attempt loop, lines ~213-279 of the old file) and adapt:

```python
"""Persistence backend: PostgreSQL primary, in-memory fallback. Same dict shapes both ways."""
import time
from contextlib import contextmanager

from config import Config

_PG_OK = False
try:
    import psycopg
    from psycopg_pool import ConnectionPool
    _PG_OK = True
except ImportError:
    psycopg = None
    ConnectionPool = None

_MEM_TABLES = (
    "users", "locations", "grievances", "evidence",
    "timeline_events", "recurring_groups", "notices", "audit_log",
)

STATE = {"mode": "memory", "pg_pool": None, "mem": {}, "seq": {}}


def reset_memory_store() -> None:
    STATE["mode"] = "memory"
    STATE["pg_pool"] = None
    STATE["mem"] = {t: [] for t in _MEM_TABLES}
    STATE["seq"] = {}


def is_memory() -> bool:
    return STATE["mode"] == "memory"


@contextmanager
def connection():
    if STATE["mode"] != "postgres" or not STATE["pg_pool"]:
        raise RuntimeError("pool.connection() called in memory mode")
    with STATE["pg_pool"].connection() as conn:
        yield conn


def next_seq(name: str) -> int:
    if STATE["mode"] == "postgres":
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE SEQUENCE IF NOT EXISTS %s" % f"seq_{name}")
                cur.execute("SELECT nextval(%s)", (f"seq_{name}",))
                val = cur.fetchone()[0]
            conn.commit()
            return int(val)
    STATE["seq"][name] = STATE["seq"].get(name, 0) + 1
    return STATE["seq"][name]


def init_db() -> None:
    from db import schema

    reset_memory_store()
    dsn = Config.DATABASE_URL
    if dsn and _PG_OK:
        for attempt in range(1, 4):
            try:
                STATE["pg_pool"] = ConnectionPool(
                    dsn, min_size=0, max_size=2, open=True, timeout=10,
                    max_idle=120, max_lifetime=600,
                    kwargs={"connect_timeout": 5, "keepalives": 1,
                            "keepalives_idle": 30, "keepalives_interval": 5,
                            "keepalives_count": 3, "prepare_threshold": None},
                    check=ConnectionPool.check_connection,
                )
                with STATE["pg_pool"].connection(timeout=10) as conn:
                    schema.ensure(conn)
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                STATE["mode"] = "postgres"
                print(f"[db] Postgres connected (attempt {attempt})")
                return
            except Exception as e:  # noqa: BLE001
                print(f"[db] Postgres attempt {attempt}/3 failed: {type(e).__name__}: {e}")
                if STATE["pg_pool"]:
                    try:
                        STATE["pg_pool"].close(timeout=2)
                    except Exception:  # noqa: BLE001
                        pass
                    STATE["pg_pool"] = None
                if attempt < 3:
                    time.sleep(3)
        print("[db] Postgres unavailable — using in-memory mode")
    STATE["mode"] = "memory"
```

- [ ] **Step 3: Run the existing tests to confirm nothing imports break**

Run: `pytest -q`
Expected: PASS (only the skipped placeholder).

- [ ] **Step 4: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db"
git commit -m "feat(unipulse): db pool with postgres + in-memory backends"
```

---

### Task 4: Trim `services/auth_service.py` to DB-backed login

**Files:**
- Modify: `services/auth_service.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `db.users.get_by_username(username: str) -> dict | None` (defined in Task 10; returns `{"id","username","display_name","role","pin_hash","department","contact","is_active"}`). Until Task 10 lands, `login()` imports it lazily inside the function.
- Produces:
  - `auth_service.hash_pin(pin: str) -> str`, `verify_pin(plain, hashed) -> bool`
  - `auth_service.create_access_token(user: dict) -> str`, `create_refresh_token(user_id: str) -> str`
  - `auth_service.decode_access_token(token) -> dict` / `decode_refresh_token(token) -> dict` (raise `AuthError`)
  - `auth_service.AuthError`
  - `auth_service.login(username: str, pin: str) -> LoginResult` where `LoginResult` has `.success: bool`, `.error: str|None`, `.user: dict`, `.access_token: str`, `.refresh_token: str`
  - `auth_service.check_rate_limit(key: str) -> bool` (True = allowed), simple in-memory sliding window, 5 attempts / 300 s.

- [ ] **Step 1: Write the failing test `tests/test_auth.py`**

```python
from services import auth_service


def test_pin_hash_roundtrip():
    h = auth_service.hash_pin("1234")
    assert h != "1234"
    assert auth_service.verify_pin("1234", h)
    assert not auth_service.verify_pin("0000", h)


def test_access_token_roundtrip():
    tok = auth_service.create_access_token(
        {"username": "admin", "display_name": "Sir", "role": "admin", "department": None}
    )
    payload = auth_service.decode_access_token(tok)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"


def test_decode_rejects_garbage():
    import pytest
    with pytest.raises(auth_service.AuthError):
        auth_service.decode_access_token("not-a-token")


def test_rate_limit_trips_after_five():
    key = "u@1.2.3.4"
    assert all(auth_service.check_rate_limit(key) for _ in range(5))
    assert auth_service.check_rate_limit(key) is False
```

- [ ] **Step 2: Run it — fails**

Run: `pytest tests/test_auth.py -q`
Expected: FAIL (import / attribute errors).

- [ ] **Step 3: Rewrite `services/auth_service.py`**

Keep the JWT + bcrypt helpers from the current file (they are already correct); replace `login()` / `refresh_access_token()`:

```python
"""Authentication: PIN hashing, JWT, DB-backed login, login rate-limit."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import bcrypt
import jwt

from config import Config

_ALG = "HS256"
_ACCESS_TTL = 15 * 60
_REFRESH_TTL = 7 * 24 * 3600


class AuthError(Exception):
    pass


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:  # noqa: BLE001
        return False


def create_access_token(user: dict) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": user["username"], "name": user.get("display_name", user["username"]),
         "role": user["role"], "dept": user.get("department"),
         "iat": now, "exp": now + _ACCESS_TTL, "type": "access"},
        Config.JWT_SECRET, algorithm=_ALG,
    )


def create_refresh_token(user_id: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + _REFRESH_TTL, "type": "refresh"},
        Config.JWT_SECRET, algorithm=_ALG,
    )


def _decode(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=[_ALG])
    except jwt.ExpiredSignatureError:
        raise AuthError("token expired")
    except jwt.InvalidTokenError as e:  # noqa: BLE001
        raise AuthError(f"invalid token: {e}")
    if payload.get("type") != expected_type:
        raise AuthError("wrong token type")
    return payload


def decode_access_token(token: str) -> dict:
    return _decode(token, "access")


def decode_refresh_token(token: str) -> dict:
    return _decode(token, "refresh")


@dataclass
class LoginResult:
    success: bool
    user: dict = field(default_factory=dict)
    access_token: str = ""
    refresh_token: str = ""
    error: str | None = None


def login(username: str, pin: str) -> LoginResult:
    from db import users
    u = users.get_by_username(username.lower().strip())
    if not u or not u.get("is_active", True):
        return LoginResult(False, error="No such account")
    if not verify_pin(pin, u["pin_hash"]):
        return LoginResult(False, error="Incorrect PIN")
    return LoginResult(
        True, user=u,
        access_token=create_access_token(u),
        refresh_token=create_refresh_token(u["username"]),
    )


def refresh(refresh_token: str) -> LoginResult:
    from db import users
    payload = decode_refresh_token(refresh_token)
    u = users.get_by_username(payload["sub"])
    if not u or not u.get("is_active", True):
        return LoginResult(False, error="Account inactive")
    return LoginResult(
        True, user=u,
        access_token=create_access_token(u),
        refresh_token=create_refresh_token(u["username"]),
    )


# ── login rate limit (in-memory sliding window) ──────────────────────────────
_ATTEMPTS: dict[str, list[float]] = {}
_MAX, _WINDOW = 5, 300.0


def check_rate_limit(key: str) -> bool:
    now = time.time()
    bucket = [t for t in _ATTEMPTS.get(key, []) if now - t < _WINDOW]
    bucket.append(now)
    _ATTEMPTS[key] = bucket
    return len(bucket) <= _MAX
```

- [ ] **Step 4: Run the test — passes**

Run: `pytest tests/test_auth.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/services/auth_service.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_auth.py"
git commit -m "feat(unipulse): DB-backed login + JWT + rate limit"
```

---

### Task 5: App factory + auth blueprint + base templates

**Files:**
- Create: `app.py` (replace), `wsgi.py`, `blueprints/__init__.py`, `blueprints/auth/__init__.py`, `templates/base_faculty.html`, `templates/base_admin.html`, `static/css/app.css`
- Modify: `templates/login.html`
- Delete: `templates/base.html` (replaced by the two base templates)

**Interfaces:**
- Consumes: `auth_service.login/refresh/decode_access_token`, `db.pool.init_db`, `domain.rbac.has_permission` (Task 9 — imported lazily in the context processor until then).
- Produces:
  - `app.create_app() -> Flask`
  - `flask.g.current_user` populated by `@app.before_request` — dict `{username, display_name, role, department}` or `None`
  - Jinja globals: `current_user`, `can(perm: str) -> bool`, `GLB` (dict)
  - Routes: `GET/POST /login`, `GET /logout`, `POST /auth/refresh`
  - Cookie names `up_access`, `up_refresh`; helper `blueprints.auth._set_cookies(resp, access, refresh)` / `_clear_cookies(resp)`

- [ ] **Step 1: Write `app.py`**

```python
"""UniPulse — GL Bajaj campus infrastructure intelligence. Flask app factory."""
import os

from flask import Flask, g, redirect, request, url_for

from config import Config
from domain.constants import GLB
from services import auth_service


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    from db import pool
    pool.init_db()

    from db import seeds
    seeds.run()

    from blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    @app.before_request
    def _load_user():
        g.current_user = None
        token = request.cookies.get("up_access")
        if not token:
            return
        try:
            p = auth_service.decode_access_token(token)
            g.current_user = {"username": p["sub"], "display_name": p.get("name", p["sub"]),
                              "role": p["role"], "department": p.get("dept")}
        except auth_service.AuthError:
            g.current_user = None

    @app.context_processor
    def _inject():
        from domain.rbac import has_permission
        user = g.get("current_user")
        return {
            "current_user": user,
            "GLB": GLB,
            "can": (lambda perm: bool(user) and has_permission(user["role"], perm)),
        }

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "db": pool.STATE["mode"]}

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
                     debug=os.environ.get("FLASK_DEBUG") == "1")
```

- [ ] **Step 2: Write `wsgi.py`**

```python
from app import create_app

app = create_app()
```

- [ ] **Step 3: Write `blueprints/__init__.py`** (empty file)

- [ ] **Step 4: Write `blueprints/auth/__init__.py`**

```python
"""Auth blueprint: login / logout / token refresh."""
from flask import Blueprint, g, make_response, redirect, render_template, request, url_for

from config import Config
from services import auth_service

bp = Blueprint("auth", __name__, template_folder="../../templates")

_ACCESS, _REFRESH = "up_access", "up_refresh"
_SECURE = Config.is_production()


def _set_cookies(resp, access: str, refresh: str):
    resp.set_cookie(_ACCESS, access, max_age=15 * 60, httponly=True,
                    samesite="Strict", secure=_SECURE, path="/")
    resp.set_cookie(_REFRESH, refresh, max_age=7 * 24 * 3600, httponly=True,
                    samesite="Strict", secure=_SECURE, path="/auth/refresh")
    return resp


def _clear_cookies(resp):
    resp.set_cookie(_ACCESS, "", expires=0, path="/")
    resp.set_cookie(_REFRESH, "", expires=0, path="/auth/refresh")
    return resp


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if g.get("current_user"):
            return redirect("/admin" if g.current_user["role"] == "admin" else "/")
        return render_template("login.html", error=None)

    username = (request.form.get("username") or "").strip()
    pin = (request.form.get("pin") or "").strip()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if not auth_service.check_rate_limit(f"{username.lower()}@{ip}"):
        return render_template("login.html", error="Too many attempts — wait a few minutes."), 429

    result = auth_service.login(username, pin)
    if not result.success:
        return render_template("login.html", error=result.error), 401

    target = "/admin" if result.user["role"] == "admin" else "/"
    resp = make_response(redirect(target))
    return _set_cookies(resp, result.access_token, result.refresh_token)


@bp.get("/logout")
def logout():
    return _clear_cookies(make_response(redirect(url_for("auth.login"))))


@bp.post("/auth/refresh")
def refresh():
    tok = request.cookies.get(_REFRESH)
    if not tok:
        return {"error": "no refresh token"}, 401
    try:
        result = auth_service.refresh(tok)
    except auth_service.AuthError as e:
        resp = make_response({"error": str(e)}, 401)
        return _clear_cookies(resp)
    if not result.success:
        return _clear_cookies(make_response({"error": result.error}, 401))
    resp = make_response({"ok": True, "role": result.user["role"]})
    return _set_cookies(resp, result.access_token, result.refresh_token)
```

- [ ] **Step 5: Write `templates/base_faculty.html`** (stub — real UI in Phase B)

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}UniPulse{% endblock %} · {{ GLB.short }}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
</head>
<body class="faculty">
  <header class="topbar"><strong>UniPulse</strong> · {{ GLB.short }}
    {% if current_user %}<a href="/logout" class="right">Log out</a>{% endif %}
  </header>
  <main>{% block content %}{% endblock %}</main>
</body>
</html>
```

- [ ] **Step 6: Write `templates/base_admin.html`** — same as Step 5 but `<body class="admin">` and title `{% block title %}Admin{% endblock %} · UniPulse`.

- [ ] **Step 7: Write `static/css/app.css`**

```css
:root { --glb-navy:#0b2a5b; --glb-blue:#1e5fbf; --ink:#1a1a1a; --muted:#667; --line:#e3e6ec; }
* { box-sizing: border-box; }
body { margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; color:var(--ink); background:#f6f7f9; }
.topbar { background:var(--glb-navy); color:#fff; padding:12px 16px; }
.topbar a { color:#cfe0ff; text-decoration:none; }
.topbar .right { float:right; }
main { max-width:960px; margin:0 auto; padding:20px 16px; }
.error { background:#fde8e8; color:#9b1c1c; padding:10px 12px; border-radius:6px; }
button, .btn { background:var(--glb-blue); color:#fff; border:0; border-radius:6px; padding:10px 16px; font-size:15px; cursor:pointer; }
input { padding:10px; border:1px solid var(--line); border-radius:6px; width:100%; font-size:15px; }
label { display:block; margin:12px 0 4px; font-weight:600; }
```

- [ ] **Step 8: Rewrite `templates/login.html`** — a plain page extending `base_faculty.html`:

```html
{% extends "base_faculty.html" %}
{% block title %}Sign in{% endblock %}
{% block content %}
<h1>Sign in to UniPulse</h1>
<p class="muted">{{ GLB.name }}</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post" action="/login" style="max-width:360px">
  <label for="username">Username</label>
  <input id="username" name="username" autocomplete="username" required>
  <label for="pin">PIN</label>
  <input id="pin" name="pin" type="password" autocomplete="current-password" required>
  <p style="margin-top:16px"><button type="submit">Sign in</button></p>
</form>
<p class="muted">Faculty accounts are created by the campus admin.</p>
{% endblock %}
```

- [ ] **Step 9: Delete `templates/base.html`**

```bash
rm -f templates/base.html
```

- [ ] **Step 10: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/app.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/wsgi.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/blueprints" \
        "OneDrive/Desktop/unipulse/unipulse-campus/templates" \
        "OneDrive/Desktop/unipulse/unipulse-campus/static"
git commit -m "feat(unipulse): app factory + auth blueprint + base templates"
```

---

## Phase A — Data Foundations

### Task 6: `domain/constants.py`

**Files:**
- Modify: `domain/constants.py` (full replace)
- Test: `tests/test_constants.py`, `tests/test_boot.py` (fill in)

**Interfaces:**
- Produces (all module-level):
  - `CATEGORIES: list[str]` (the 6, in order)
  - `SEVERITIES: list[str]` = `["low","medium","high"]`
  - `STATUSES: list[str]` (the 7, in order)
  - `STATUS_TRANSITIONS: dict[str, list[str]]` — allowed next statuses per status (+ reopen)
  - `RESPONSIBLE_UNITS: dict[str, list[str]]` — `{"College": [...6], "Academics": ["Class","Lab"]}`
  - `RESPONSIBLE_UNITS_FLAT: list[str]`
  - `LOCATION_TYPES: list[dict]` — `[{"key","name","drilldown": bool}]`
  - `OUTER_AREA_SUBZONES: list[str]`
  - `ACADEMICS_BLOCKS: list[str]` = `["Block A","Block B","Block C","Block D"]`
  - `ACADEMICS_FLOORS: list[str]` = `["Ground Floor","1st Floor","2nd Floor","3rd Floor","4th Floor"]`
  - `SLA_HOURS: dict[str, int]` keyed by category
  - `PULSE_DOMAINS: list[dict]` — `[{"key","name","categories": [...], "location_type": str|None, "sub_zone": str|None}]`
  - `RECURRING_WINDOW_DAYS = 14`, `GAP_THRESHOLD = 4`, `CODE_PREFIX = "GLB-CAMP-"`, `CODE_PAD = 5`
  - `GLB: dict` — `{"name","short","product","email_domain","theme_navy","theme_blue"}`

- [ ] **Step 1: Write `tests/test_constants.py`**

```python
from domain import constants as c


def test_six_categories_in_order():
    assert c.CATEGORIES == ["Electric", "Plumbing", "Civil", "Mechanical", "Power", "IT / Network"]


def test_seven_statuses_in_order():
    assert c.STATUSES == ["reported", "verified", "assigned", "in_progress",
                          "resolved", "admin_verified", "closed"]


def test_forward_transitions_are_single_step():
    for i, s in enumerate(c.STATUSES[:-1]):
        assert c.STATUSES[i + 1] in c.STATUS_TRANSITIONS[s]
    assert c.STATUS_TRANSITIONS["closed"] == []
    assert "in_progress" in c.STATUS_TRANSITIONS["resolved"]        # reopen
    assert "in_progress" in c.STATUS_TRANSITIONS["admin_verified"]  # reopen


def test_responsible_units():
    assert c.RESPONSIBLE_UNITS["College"] == ["Infrastructure", "Sanitation", "Housekeeping",
                                              "Landscaping", "Mess", "Parking"]
    assert c.RESPONSIBLE_UNITS["Academics"] == ["Class", "Lab"]
    assert set(c.RESPONSIBLE_UNITS_FLAT) == {"Infrastructure", "Sanitation", "Housekeeping",
                                             "Landscaping", "Mess", "Parking", "Class", "Lab"}


def test_sla_hours_cover_every_category():
    assert set(c.SLA_HOURS) == set(c.CATEGORIES)
    assert all(isinstance(v, int) and v > 0 for v in c.SLA_HOURS.values())


def test_glb_identity():
    assert c.GLB["name"] == "GL Bajaj Institute of Technology and Management"
    assert c.CODE_PREFIX == "GLB-CAMP-"
```

- [ ] **Step 2: Run — fails**

Run: `pytest tests/test_constants.py -q` → FAIL.

- [ ] **Step 3: Write `domain/constants.py`**

```python
"""Domain constants for UniPulse (GL Bajaj campus). Stdlib-only."""

CATEGORIES = ["Electric", "Plumbing", "Civil", "Mechanical", "Power", "IT / Network"]
SEVERITIES = ["low", "medium", "high"]

STATUSES = ["reported", "verified", "assigned", "in_progress",
            "resolved", "admin_verified", "closed"]

STATUS_TRANSITIONS = {
    "reported":       ["verified"],
    "verified":       ["assigned"],
    "assigned":       ["in_progress"],
    "in_progress":    ["resolved"],
    "resolved":       ["admin_verified", "in_progress"],   # in_progress = reopen
    "admin_verified": ["closed", "in_progress"],           # in_progress = reopen
    "closed":         [],
}

RESPONSIBLE_UNITS = {
    "College":   ["Infrastructure", "Sanitation", "Housekeeping", "Landscaping", "Mess", "Parking"],
    "Academics": ["Class", "Lab"],
}
RESPONSIBLE_UNITS_FLAT = RESPONSIBLE_UNITS["College"] + RESPONSIBLE_UNITS["Academics"]

LOCATION_TYPES = [
    {"key": "academics_block", "name": "Academics Block", "drilldown": True},
    {"key": "hostels",         "name": "Hostels",         "drilldown": False},
    {"key": "mess_canteen",    "name": "Mess / Canteen",  "drilldown": False},
    {"key": "playground",      "name": "Playground",      "drilldown": False},
    {"key": "outer_area",      "name": "Outer Area",      "drilldown": True},
]
OUTER_AREA_SUBZONES = ["Common/Electrical", "Security", "Lawn Area", "Sewage", "Drainage"]
ACADEMICS_BLOCKS = ["Block A", "Block B", "Block C", "Block D"]
ACADEMICS_FLOORS = ["Ground Floor", "1st Floor", "2nd Floor", "3rd Floor", "4th Floor"]

SLA_HOURS = {
    "Electric": 24, "Power": 24, "Plumbing": 48,
    "Mechanical": 72, "Civil": 120, "IT / Network": 48,
}

PULSE_DOMAINS = [
    {"key": "electrical",  "name": "Electrical",      "categories": ["Electric", "Power"],   "location_type": None, "sub_zone": None},
    {"key": "water",       "name": "Water / Plumbing", "categories": ["Plumbing"],            "location_type": None, "sub_zone": None},
    {"key": "classrooms",  "name": "Classrooms",       "categories": [],                      "location_type": "academics_block", "sub_zone": None},
    {"key": "it",          "name": "IT",               "categories": ["IT / Network"],        "location_type": None, "sub_zone": None},
    {"key": "cleanliness", "name": "Cleanliness",      "categories": ["Civil"],               "location_type": None, "sub_zone": None},
    {"key": "security",    "name": "Security",         "categories": [],                      "location_type": None, "sub_zone": "Security"},
]

RECURRING_WINDOW_DAYS = 14
GAP_THRESHOLD = 4
CODE_PREFIX = "GLB-CAMP-"
CODE_PAD = 5

GLB = {
    "name": "GL Bajaj Institute of Technology and Management",
    "short": "GL Bajaj",
    "product": "UniPulse",
    "email_domain": "glbitm.ac.in",
    "theme_navy": "#0b2a5b",
    "theme_blue": "#1e5fbf",
}
```

- [ ] **Step 4: Fill in `tests/test_boot.py`**

```python
def test_app_boots_in_memory(app):
    from db import pool
    assert pool.STATE["mode"] == "memory"


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["db"] == "memory"


def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"UniPulse" in r.data
```

- [ ] **Step 5: Run — constants pass; boot test will fail until seeds exist (Task 15). Mark boot tests xfail temporarily is NOT allowed — instead run only the constants file now:**

Run: `pytest tests/test_constants.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/domain/constants.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_constants.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_boot.py"
git commit -m "feat(unipulse): campus domain constants"
```

---

### Task 7: `domain/models.py`

**Files:**
- Modify: `domain/models.py` (full replace)
- Test: covered indirectly by `db/` tests; add `tests/test_models.py` for the two helpers.

**Interfaces:**
- Produces dataclasses (all fields typed, `from __future__ import annotations`):
  - `User(id, username, display_name, role, department, contact, is_active, created_at, created_by, pin_hash=None)`
  - `Location(id, parent_id, location_type, name, full_path, is_active)`
  - `Grievance(...)` — every column from spec §4 `grievances`, with `to_public_dict()` (drops nothing sensitive here — reporter contact isn't on the row) and `to_row()` helpers
  - `Evidence(id, grievance_id, kind, image_url, image_key, thumbnail_url, note, uploaded_by, uploaded_at)`
  - `TimelineEvent(id, grievance_id, event_type, from_value, to_value, actor, actor_role, note, created_at)`
  - `RecurringGroup(id, location_label, category, title, report_count, reporter_count, first_reported_at, last_reported_at, status, primary_grievance_id)`
  - `Notice(id, title, body, audience, created_by, created_at, is_published, expires_at)`
  - Helper `build_location_label(location_type, block_no, floor, room, sub_zone, *, type_names: dict) -> str`
  - Helper `recurring_key(location_label: str, category: str) -> str` → `f"{location_label}|{category}"` lowercased/stripped

- [ ] **Step 1: Write `tests/test_models.py`**

```python
from domain.models import build_location_label, recurring_key

_NAMES = {"academics_block": "Academics Block", "hostels": "Hostels",
          "mess_canteen": "Mess / Canteen", "playground": "Playground",
          "outer_area": "Outer Area"}


def test_location_label_academics_full():
    got = build_location_label("academics_block", "Block B", "2nd Floor", "204", None,
                               type_names=_NAMES)
    assert got == "Academics Block > Block B > 2nd Floor > Room 204"


def test_location_label_outer_area():
    got = build_location_label("outer_area", None, None, None, "Security", type_names=_NAMES)
    assert got == "Outer Area > Security"


def test_location_label_flat():
    assert build_location_label("playground", None, None, None, None, type_names=_NAMES) == "Playground"


def test_recurring_key_is_normalised():
    assert recurring_key("  Academics Block > Block B > 2nd Floor > Room 204 ", "Electric") \
        == "academics block > block b > 2nd floor > room 204|electric"
```

- [ ] **Step 2: Run — fails.** `pytest tests/test_models.py -q` → FAIL.

- [ ] **Step 3: Write `domain/models.py`**

```python
"""Canonical dataclasses + label helpers. Stdlib-only."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    id: int
    username: str
    display_name: str
    role: str
    department: Optional[str]
    contact: Optional[str]
    is_active: bool
    created_at: float
    created_by: Optional[str]
    pin_hash: Optional[str] = None


@dataclass
class Location:
    id: int
    parent_id: Optional[int]
    location_type: str
    name: str
    full_path: str
    is_active: bool = True


@dataclass
class Grievance:
    id: int
    code: str
    reporter_id: Optional[int]
    reporter_name: str
    title: str
    description: str
    category: Optional[str]
    category_confirmed: bool
    severity: Optional[str]
    priority_score: int
    status: str
    location_type: str
    block_no: Optional[str]
    floor: Optional[str]
    room: Optional[str]
    sub_zone: Optional[str]
    location_label: str
    responsible_unit: Optional[str]
    assignee: Optional[str]
    assigned_at: Optional[float]
    due_at: Optional[float]
    recurring_group_id: Optional[int]
    ai_summary: Optional[str]
    ai_confidence: Optional[int]
    primary_photo_url: Optional[str]
    thumbnail_url: Optional[str]
    created_at: float
    updated_at: float
    resolved_at: Optional[float] = None
    closed_at: Optional[float] = None


@dataclass
class Evidence:
    id: int
    grievance_id: int
    kind: str
    image_url: Optional[str]
    image_key: Optional[str]
    thumbnail_url: Optional[str]
    note: Optional[str]
    uploaded_by: str
    uploaded_at: float


@dataclass
class TimelineEvent:
    id: int
    grievance_id: int
    event_type: str
    from_value: Optional[str]
    to_value: Optional[str]
    actor: str
    actor_role: Optional[str]
    note: Optional[str]
    created_at: float


@dataclass
class RecurringGroup:
    id: int
    location_label: str
    category: str
    title: str
    report_count: int
    reporter_count: int
    first_reported_at: float
    last_reported_at: float
    status: str
    primary_grievance_id: Optional[int]


@dataclass
class Notice:
    id: int
    title: str
    body: str
    audience: str
    created_by: str
    created_at: float
    is_published: bool
    expires_at: Optional[float] = None


def build_location_label(location_type, block_no, floor, room, sub_zone, *, type_names):
    base = type_names.get(location_type, location_type)
    if location_type == "academics_block":
        parts = [base]
        if block_no:
            parts.append(block_no)
        if floor:
            parts.append(floor)
        if room:
            parts.append(f"Room {room}")
        return " > ".join(parts)
    if location_type == "outer_area" and sub_zone:
        return f"{base} > {sub_zone}"
    return base


def recurring_key(location_label: str, category: str) -> str:
    return f"{(location_label or '').strip().lower()}|{(category or '').strip().lower()}"
```

- [ ] **Step 4: Run — passes.** `pytest tests/test_models.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/domain/models.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_models.py"
git commit -m "feat(unipulse): campus domain dataclasses + label helpers"
```

---

### Task 8: `domain/rbac.py`

**Files:**
- Create: `domain/rbac.py`
- Test: `tests/test_rbac.py`

**Interfaces:**
- Produces:
  - Permission string constants: `GRIEVANCE_CREATE, GRIEVANCE_VIEW_OWN, GRIEVANCE_VIEW_ALL, GRIEVANCE_VERIFY, GRIEVANCE_CORRECT_CATEGORY, GRIEVANCE_ASSIGN, GRIEVANCE_CHANGE_STATUS, GRIEVANCE_VERIFY_RESOLUTION, GRIEVANCE_CLOSE, ANALYTICS_VIEW, NOTICE_MANAGE, USER_MANAGE, LOCATION_MANAGE, AUDIT_VIEW` (values are dotted slugs, e.g. `"grievance.create"`)
  - `ROLE_PERMISSIONS: dict[str, set[str]]` for `"reporter"` and `"admin"`
  - `has_permission(role: str | None, perm: str) -> bool`
  - `require_permission(perm: str)` — Flask route decorator: 403 JSON if `request.path` endswith `/data` or method != GET, else redirect to `/login`; passes through if `flask.g.current_user` has the perm.

- [ ] **Step 1: Write `tests/test_rbac.py`**

```python
from domain import rbac


def test_reporter_scope():
    assert rbac.has_permission("reporter", rbac.GRIEVANCE_CREATE)
    assert rbac.has_permission("reporter", rbac.GRIEVANCE_VIEW_OWN)
    assert not rbac.has_permission("reporter", rbac.GRIEVANCE_VIEW_ALL)
    assert not rbac.has_permission("reporter", rbac.GRIEVANCE_ASSIGN)


def test_admin_has_everything():
    everything = set().union(*rbac.ROLE_PERMISSIONS.values())
    for perm in everything:
        assert rbac.has_permission("admin", perm)


def test_unknown_role_or_none():
    assert not rbac.has_permission(None, rbac.GRIEVANCE_CREATE)
    assert not rbac.has_permission("ghost", rbac.GRIEVANCE_CREATE)


def test_require_permission_redirects_anonymous(app):
    from flask import Blueprint
    bp = Blueprint("t", __name__)

    @bp.get("/t/secret")
    @rbac.require_permission(rbac.GRIEVANCE_VIEW_ALL)
    def secret():
        return "ok"

    app.register_blueprint(bp)
    r = app.test_client().get("/t/secret")
    assert r.status_code in (301, 302)
    assert "/login" in r.headers["Location"]
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Write `domain/rbac.py`**

```python
"""Role-based access control. Stdlib + flask only (decorator)."""
from __future__ import annotations

import functools

GRIEVANCE_CREATE            = "grievance.create"
GRIEVANCE_VIEW_OWN          = "grievance.view_own"
GRIEVANCE_VIEW_ALL          = "grievance.view_all"
GRIEVANCE_VERIFY            = "grievance.verify"
GRIEVANCE_CORRECT_CATEGORY  = "grievance.correct_category"
GRIEVANCE_ASSIGN            = "grievance.assign"
GRIEVANCE_CHANGE_STATUS     = "grievance.change_status"
GRIEVANCE_VERIFY_RESOLUTION = "grievance.verify_resolution"
GRIEVANCE_CLOSE             = "grievance.close"
ANALYTICS_VIEW             = "analytics.view"
NOTICE_MANAGE             = "notice.manage"
USER_MANAGE               = "user.manage"
LOCATION_MANAGE           = "location.manage"
AUDIT_VIEW                = "audit.view"

_REPORTER = {GRIEVANCE_CREATE, GRIEVANCE_VIEW_OWN}
_ADMIN = {
    GRIEVANCE_VIEW_ALL, GRIEVANCE_VERIFY, GRIEVANCE_CORRECT_CATEGORY, GRIEVANCE_ASSIGN,
    GRIEVANCE_CHANGE_STATUS, GRIEVANCE_VERIFY_RESOLUTION, GRIEVANCE_CLOSE,
    ANALYTICS_VIEW, NOTICE_MANAGE, USER_MANAGE, LOCATION_MANAGE, AUDIT_VIEW,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "reporter": set(_REPORTER),
    "admin": set(_REPORTER) | _ADMIN,
}


def has_permission(role, perm: str) -> bool:
    return bool(role) and perm in ROLE_PERMISSIONS.get(role, set())


def require_permission(perm: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import g, redirect, request, jsonify
            user = g.get("current_user")
            if user and has_permission(user["role"], perm):
                return fn(*args, **kwargs)
            wants_json = request.method != "GET" or request.path.endswith("/data") \
                or request.path.startswith("/api/")
            if wants_json:
                return jsonify({"error": "forbidden", "need": perm}), 403
            return redirect("/login")
        return wrapper
    return deco
```

- [ ] **Step 4: Run — passes.**

- [ ] **Step 5: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/domain/rbac.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_rbac.py"
git commit -m "feat(unipulse): RBAC permission map + require_permission"
```

---

### Task 9: `db/schema.py` — DDL

**Files:**
- Create: `db/schema.py`
- Test: none directly (exercised by the Postgres path; memory mode needs no DDL). Add a syntax check to `tests/test_seeds.py` later.

**Interfaces:**
- Produces: `schema.ensure(conn) -> None` — runs `CREATE TABLE IF NOT EXISTS` + indexes + the `grievances.status` CHECK for all 8 tables from spec §4. Idempotent.
- Produces: `schema.DDL: str` (the raw SQL, for inspection/tests).

- [ ] **Step 1: Write `db/schema.py`**

```python
"""PostgreSQL DDL. Idempotent. Memory mode does not use this."""

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('reporter','admin')),
    pin_hash      TEXT NOT NULL,
    department    TEXT,
    contact       TEXT,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    DOUBLE PRECISION,
    created_by    TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TABLE IF NOT EXISTS locations (
    id            BIGSERIAL PRIMARY KEY,
    parent_id     BIGINT REFERENCES locations(id) ON DELETE CASCADE,
    location_type TEXT NOT NULL,
    name          TEXT NOT NULL,
    full_path     TEXT UNIQUE NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_locations_type ON locations(location_type);

CREATE TABLE IF NOT EXISTS recurring_groups (
    id                   BIGSERIAL PRIMARY KEY,
    location_label       TEXT NOT NULL,
    category             TEXT NOT NULL,
    title                TEXT,
    report_count         INTEGER DEFAULT 0,
    reporter_count       INTEGER DEFAULT 0,
    first_reported_at    DOUBLE PRECISION,
    last_reported_at     DOUBLE PRECISION,
    status               TEXT DEFAULT 'active' CHECK (status IN ('active','resolved')),
    primary_grievance_id BIGINT
);
CREATE INDEX IF NOT EXISTS idx_recurring_key ON recurring_groups(location_label, category);

CREATE TABLE IF NOT EXISTS grievances (
    id                 BIGSERIAL PRIMARY KEY,
    code               TEXT UNIQUE NOT NULL,
    reporter_id        BIGINT REFERENCES users(id),
    reporter_name      TEXT,
    title              TEXT,
    description        TEXT NOT NULL,
    category           TEXT,
    category_confirmed BOOLEAN DEFAULT FALSE,
    severity           TEXT,
    priority_score     INTEGER DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'reported'
                       CHECK (status IN ('reported','verified','assigned','in_progress',
                                         'resolved','admin_verified','closed')),
    location_type      TEXT,
    block_no           TEXT,
    floor              TEXT,
    room               TEXT,
    sub_zone           TEXT,
    location_label     TEXT,
    responsible_unit   TEXT,
    assignee           TEXT,
    assigned_at        DOUBLE PRECISION,
    due_at             DOUBLE PRECISION,
    recurring_group_id BIGINT REFERENCES recurring_groups(id),
    ai_summary         TEXT,
    ai_confidence      INTEGER,
    primary_photo_url  TEXT,
    thumbnail_url      TEXT,
    created_at         DOUBLE PRECISION,
    updated_at         DOUBLE PRECISION,
    resolved_at        DOUBLE PRECISION,
    closed_at          DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_grievances_status   ON grievances(status);
CREATE INDEX IF NOT EXISTS idx_grievances_category ON grievances(category);
CREATE INDEX IF NOT EXISTS idx_grievances_created  ON grievances(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_grievances_recurring ON grievances(recurring_group_id);

CREATE TABLE IF NOT EXISTS evidence (
    id            BIGSERIAL PRIMARY KEY,
    grievance_id  BIGINT NOT NULL REFERENCES grievances(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL CHECK (kind IN ('report','resolution_before','resolution_after')),
    image_url     TEXT,
    image_key     TEXT,
    thumbnail_url TEXT,
    note          TEXT,
    uploaded_by   TEXT,
    uploaded_at   DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_evidence_grievance ON evidence(grievance_id);

CREATE TABLE IF NOT EXISTS timeline_events (
    id            BIGSERIAL PRIMARY KEY,
    grievance_id  BIGINT NOT NULL REFERENCES grievances(id) ON DELETE CASCADE,
    event_type    TEXT NOT NULL,
    from_value    TEXT,
    to_value      TEXT,
    actor         TEXT,
    actor_role    TEXT,
    note          TEXT,
    created_at    DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_timeline_grievance ON timeline_events(grievance_id);

CREATE TABLE IF NOT EXISTS notices (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    body         TEXT,
    audience     TEXT DEFAULT 'all',
    created_by   TEXT,
    created_at   DOUBLE PRECISION,
    is_published BOOLEAN DEFAULT FALSE,
    expires_at   DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor       TEXT,
    action      TEXT,
    target_type TEXT,
    target_id   TEXT,
    detail      JSONB,
    created_at  DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
"""


def ensure(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
```

- [ ] **Step 2: Sanity — import it**

Run: `python -c "from db import schema; assert 'CREATE TABLE IF NOT EXISTS grievances' in schema.DDL; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db/schema.py"
git commit -m "feat(unipulse): postgres schema DDL"
```

---

### Task 10: `db/users.py`

**Files:**
- Create: `db/users.py`
- Test: `tests/test_users_db.py`

**Interfaces:**
- Consumes: `pool.STATE`, `pool.is_memory()`, `pool.next_seq()`, `pool.connection()`.
- Produces:
  - `users.get_by_username(username: str) -> dict | None`
  - `users.get_by_id(uid: int) -> dict | None`
  - `users.list_all(role: str | None = None) -> list[dict]`
  - `users.create(username, display_name, role, pin_hash, department=None, contact=None, created_by=None) -> dict` — raises `ValueError` on duplicate username
  - `users.set_active(uid: int, active: bool) -> None`
  - `users.set_pin(uid: int, pin_hash: str) -> None`
  - dict shape: `{id, username, display_name, role, pin_hash, department, contact, is_active, created_at, created_by}`

- [ ] **Step 1: Write `tests/test_users_db.py`**

```python
import pytest
from db import users
from services.auth_service import hash_pin


def test_create_and_fetch(app):
    u = users.create("prof.rao", "Prof Rao", "reporter", hash_pin("1111"), department="CSE")
    assert u["id"] > 0
    assert users.get_by_username("prof.rao")["display_name"] == "Prof Rao"
    assert users.get_by_id(u["id"])["role"] == "reporter"


def test_duplicate_username_rejected(app):
    users.create("dup", "One", "reporter", hash_pin("1"))
    with pytest.raises(ValueError):
        users.create("dup", "Two", "reporter", hash_pin("2"))


def test_list_by_role(app):
    users.create("a1", "A1", "admin", hash_pin("1"))
    users.create("r1", "R1", "reporter", hash_pin("1"))
    assert {u["username"] for u in users.list_all(role="reporter")} == {"r1"}


def test_set_active_and_pin(app):
    u = users.create("x", "X", "reporter", hash_pin("1"))
    users.set_active(u["id"], False)
    assert users.get_by_id(u["id"])["is_active"] is False
    users.set_pin(u["id"], hash_pin("2"))
    from services.auth_service import verify_pin
    assert verify_pin("2", users.get_by_id(u["id"])["pin_hash"])
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Write `db/users.py`**

```python
"""User account persistence (faculty + admin)."""
import time

from db import pool

_COLS = ("id", "username", "display_name", "role", "pin_hash",
         "department", "contact", "is_active", "created_at", "created_by")


def _mem():
    return pool.STATE["mem"]["users"]


def _row(d: dict) -> dict:
    return {k: d.get(k) for k in _COLS}


def get_by_username(username: str):
    username = (username or "").lower().strip()
    if pool.is_memory():
        return next((_row(u) for u in _mem() if u["username"] == username), None)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM users WHERE username=%s", (username,))
        r = cur.fetchone()
        return dict(zip(_COLS, r)) if r else None


def get_by_id(uid: int):
    if pool.is_memory():
        return next((_row(u) for u in _mem() if u["id"] == uid), None)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM users WHERE id=%s", (uid,))
        r = cur.fetchone()
        return dict(zip(_COLS, r)) if r else None


def list_all(role: str | None = None):
    if pool.is_memory():
        rows = [_row(u) for u in _mem()]
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLS)} FROM users ORDER BY display_name")
            rows = [dict(zip(_COLS, r)) for r in cur.fetchall()]
    return [r for r in rows if role is None or r["role"] == role]


def create(username, display_name, role, pin_hash, department=None, contact=None, created_by=None):
    username = username.lower().strip()
    if get_by_username(username):
        raise ValueError(f"username {username!r} already exists")
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("users"), "username": username, "display_name": display_name,
               "role": role, "pin_hash": pin_hash, "department": department, "contact": contact,
               "is_active": True, "created_at": now, "created_by": created_by}
        _mem().append(row)
        return _row(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO users (username, display_name, role, pin_hash, department,
                                  contact, is_active, created_at, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,TRUE,%s,%s) RETURNING id""",
            (username, display_name, role, pin_hash, department, contact, now, created_by),
        )
        uid = cur.fetchone()[0]
        conn.commit()
    return get_by_id(uid)


def set_active(uid: int, active: bool) -> None:
    if pool.is_memory():
        for u in _mem():
            if u["id"] == uid:
                u["is_active"] = active
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET is_active=%s WHERE id=%s", (active, uid))
        conn.commit()


def set_pin(uid: int, pin_hash: str) -> None:
    if pool.is_memory():
        for u in _mem():
            if u["id"] == uid:
                u["pin_hash"] = pin_hash
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET pin_hash=%s WHERE id=%s", (pin_hash, uid))
        conn.commit()
```

- [ ] **Step 4: Run — passes.** `pytest tests/test_users_db.py -q`

- [ ] **Step 5: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db/users.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_users_db.py"
git commit -m "feat(unipulse): users persistence"
```

---

### Task 11: `db/locations.py`

**Files:**
- Create: `db/locations.py`
- Test: `tests/test_locations_db.py`

**Interfaces:**
- Produces:
  - `locations.seed() -> None` — idempotent; inserts the 5 types + 5 outer-area sub-zones + Academics blocks (A–D) + floors (Ground–4th, one set, `parent_id` NULL — floors are shared, not per-block, for MVP simplicity). Keyed on `full_path` uniqueness.
  - `locations.list_all(active_only=True) -> list[dict]` — `{id, parent_id, location_type, name, full_path, is_active}`
  - `locations.picker() -> dict` — `{"types": [...LOCATION_TYPES], "outer_area_subzones": [...], "academics_blocks": [...], "academics_floors": [...]}` (drawn from DB where seeded, else from constants)
  - `locations.create(location_type, name, full_path, parent_id=None) -> dict` (raises `ValueError` on dup `full_path`)
  - `locations.set_active(loc_id, active) -> None`

- [ ] **Step 1: Write `tests/test_locations_db.py`**

```python
from db import locations


def test_seed_is_idempotent(app):
    locations.seed()
    n1 = len(locations.list_all())
    locations.seed()
    assert len(locations.list_all()) == n1
    assert n1 >= 10  # 5 types + 5 subzones minimum


def test_picker_shape(app):
    locations.seed()
    p = locations.picker()
    assert [t["name"] for t in p["types"]] == ["Academics Block", "Hostels", "Mess / Canteen",
                                               "Playground", "Outer Area"]
    assert "Security" in p["outer_area_subzones"]
    assert "Block A" in p["academics_blocks"]
    assert "2nd Floor" in p["academics_floors"]


def test_admin_can_add_block(app):
    locations.seed()
    loc = locations.create("block", "Block E", "Academics Block > Block E")
    assert loc["id"] > 0
    assert "Block E" in locations.picker()["academics_blocks"]
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Write `db/locations.py`**

```python
"""Campus location master data + picker queries."""
from db import pool
from domain.constants import (ACADEMICS_BLOCKS, ACADEMICS_FLOORS, LOCATION_TYPES,
                              OUTER_AREA_SUBZONES)

_COLS = ("id", "parent_id", "location_type", "name", "full_path", "is_active")


def _mem():
    return pool.STATE["mem"]["locations"]


def _seed_rows():
    rows = []
    for t in LOCATION_TYPES:
        rows.append(("type", t["key"], t["name"], t["name"], None))
    for z in OUTER_AREA_SUBZONES:
        rows.append(("subzone", "outer_area", z, f"Outer Area > {z}", None))
    for b in ACADEMICS_BLOCKS:
        rows.append(("kind", "block", b, f"Academics Block > {b}", None))
    for f in ACADEMICS_FLOORS:
        rows.append(("kind", "floor", f, f"Academics Block > {f}", None))
    return [{"location_type": lt, "name": nm, "full_path": fp, "parent_id": pid}
            for (_tag, lt, nm, fp, pid) in rows]


def seed() -> None:
    for r in _seed_rows():
        if _get_by_path(r["full_path"]) is None:
            create(r["location_type"], r["name"], r["full_path"], r["parent_id"])


def _get_by_path(full_path):
    if pool.is_memory():
        return next((l for l in _mem() if l["full_path"] == full_path), None)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM locations WHERE full_path=%s", (full_path,))
        r = cur.fetchone()
        return dict(zip(_COLS, r)) if r else None


def create(location_type, name, full_path, parent_id=None):
    if _get_by_path(full_path):
        raise ValueError(f"location {full_path!r} exists")
    if pool.is_memory():
        row = {"id": pool.next_seq("locations"), "parent_id": parent_id,
               "location_type": location_type, "name": name, "full_path": full_path,
               "is_active": True}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO locations (parent_id, location_type, name, full_path, is_active)
               VALUES (%s,%s,%s,%s,TRUE) RETURNING id""",
            (parent_id, location_type, name, full_path),
        )
        lid = cur.fetchone()[0]
        conn.commit()
    return _get_by_path(full_path)


def list_all(active_only=True):
    if pool.is_memory():
        rows = [dict(l) for l in _mem()]
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLS)} FROM locations ORDER BY full_path")
            rows = [dict(zip(_COLS, r)) for r in cur.fetchall()]
    return [r for r in rows if r["is_active"] or not active_only]


def set_active(loc_id, active) -> None:
    if pool.is_memory():
        for l in _mem():
            if l["id"] == loc_id:
                l["is_active"] = active
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE locations SET is_active=%s WHERE id=%s", (active, loc_id))
        conn.commit()


def picker() -> dict:
    active = list_all()
    blocks = [l["name"] for l in active if l["location_type"] == "block"] or list(ACADEMICS_BLOCKS)
    floors = [l["name"] for l in active if l["location_type"] == "floor"] or list(ACADEMICS_FLOORS)
    subs = [l["name"] for l in active if l["location_type"] == "subzone"] or list(OUTER_AREA_SUBZONES)
    return {"types": LOCATION_TYPES, "outer_area_subzones": subs,
            "academics_blocks": blocks, "academics_floors": floors}
```

- [ ] **Step 4: Run — passes.**

- [ ] **Step 5: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db/locations.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_locations_db.py"
git commit -m "feat(unipulse): campus location master data"
```

---

### Task 12: `db/grievances.py` — code generator + insert + get

**Files:**
- Create: `db/grievances.py`
- Test: `tests/test_code_generator.py`, `tests/test_grievances_db.py`

**Interfaces:**
- Produces:
  - `grievances.next_code() -> str` — `f"{CODE_PREFIX}{n:0{CODE_PAD}d}"` from `pool.next_seq("grievance")`
  - `grievances.insert(**fields) -> dict` — required: `reporter_id, reporter_name, title, description, location_type, location_label`; optional everything else; sets `code`, `status="reported"`, `created_at=updated_at=now`, defaults `priority_score=0, category_confirmed=False`. Returns the full row dict.
  - `grievances.get_by_code(code: str) -> dict | None`
  - `grievances.get_by_id(gid: int) -> dict | None`
  - `grievances.list_for_reporter(reporter_id: int) -> list[dict]` (newest first)
  - `grievances.update(gid: int, **fields) -> dict` — patches columns, bumps `updated_at`
  - `grievances.list_query(*, status=None, category=None, responsible_unit=None, location_type=None, search=None, sort="priority", limit=200) -> list[dict]`
  - `grievances.find_recurring_candidates(location_label, category, since_ts) -> list[dict]` — non-closed, same `location_label` + `category`, `created_at >= since_ts`
  - Row dict keys = every column in spec §4 `grievances`.

- [ ] **Step 1: Write `tests/test_code_generator.py`**

```python
from db import grievances


def test_code_format_and_increment(app):
    c1 = grievances.next_code()
    c2 = grievances.next_code()
    assert c1 == "GLB-CAMP-00001"
    assert c2 == "GLB-CAMP-00002"
```

- [ ] **Step 2: Write `tests/test_grievances_db.py`**

```python
import time
from db import grievances, users
from services.auth_service import hash_pin


def _reporter(app):
    return users.create("f1", "Faculty One", "reporter", hash_pin("1"))


def test_insert_sets_defaults(app):
    u = _reporter(app)
    g = grievances.insert(reporter_id=u["id"], reporter_name=u["display_name"],
                          title="Projector dead", description="Projector not working in the room",
                          location_type="academics_block",
                          location_label="Academics Block > Block B > 2nd Floor > Room 204")
    assert g["code"].startswith("GLB-CAMP-")
    assert g["status"] == "reported"
    assert g["priority_score"] == 0
    assert g["created_at"] == g["updated_at"]
    assert grievances.get_by_code(g["code"])["id"] == g["id"]


def test_list_for_reporter_newest_first(app):
    u = _reporter(app)
    a = grievances.insert(reporter_id=u["id"], reporter_name=u["display_name"], title="A",
                          description="desc one here", location_type="hostels",
                          location_label="Hostels")
    time.sleep(0.01)
    b = grievances.insert(reporter_id=u["id"], reporter_name=u["display_name"], title="B",
                          description="desc two here", location_type="hostels",
                          location_label="Hostels")
    got = grievances.list_for_reporter(u["id"])
    assert [x["code"] for x in got] == [b["code"], a["code"]]


def test_update_bumps_updated_at(app):
    u = _reporter(app)
    g = grievances.insert(reporter_id=u["id"], reporter_name="x", title="t",
                          description="description here now", location_type="playground",
                          location_label="Playground")
    time.sleep(0.01)
    g2 = grievances.update(g["id"], status="verified")
    assert g2["status"] == "verified"
    assert g2["updated_at"] > g["updated_at"]


def test_find_recurring_candidates_matches_label_and_category(app):
    u = _reporter(app)
    base = dict(reporter_id=u["id"], reporter_name="x", description="a leaking tap here",
                location_type="hostels", location_label="Hostels", category="Plumbing")
    g1 = grievances.insert(title="t1", **base)
    grievances.insert(title="t2", location_type="hostels",
                      location_label="Hostels", category="Electric",
                      reporter_id=u["id"], reporter_name="x", description="different one")
    hits = grievances.find_recurring_candidates("Hostels", "Plumbing", 0)
    assert [h["id"] for h in hits] == [g1["id"]]
```

- [ ] **Step 3: Run both — fail.**

- [ ] **Step 4: Write `db/grievances.py`**

```python
"""Grievance persistence: code generation, CRUD, queries."""
import time

from db import pool
from domain.constants import CODE_PAD, CODE_PREFIX

_COLS = (
    "id", "code", "reporter_id", "reporter_name", "title", "description", "category",
    "category_confirmed", "severity", "priority_score", "status", "location_type",
    "block_no", "floor", "room", "sub_zone", "location_label", "responsible_unit",
    "assignee", "assigned_at", "due_at", "recurring_group_id", "ai_summary",
    "ai_confidence", "primary_photo_url", "thumbnail_url", "created_at", "updated_at",
    "resolved_at", "closed_at",
)
_DEFAULTS = {
    "category": None, "category_confirmed": False, "severity": None, "priority_score": 0,
    "status": "reported", "block_no": None, "floor": None, "room": None, "sub_zone": None,
    "responsible_unit": None, "assignee": None, "assigned_at": None, "due_at": None,
    "recurring_group_id": None, "ai_summary": None, "ai_confidence": None,
    "primary_photo_url": None, "thumbnail_url": None, "resolved_at": None, "closed_at": None,
}
_REQUIRED = ("reporter_id", "reporter_name", "title", "description",
             "location_type", "location_label")


def _mem():
    return pool.STATE["mem"]["grievances"]


def next_code() -> str:
    return f"{CODE_PREFIX}{pool.next_seq('grievance'):0{CODE_PAD}d}"


def insert(**f) -> dict:
    missing = [k for k in _REQUIRED if f.get(k) in (None, "")]
    if missing:
        raise ValueError(f"missing required grievance fields: {missing}")
    now = time.time()
    row = {k: None for k in _COLS}
    row.update(_DEFAULTS)
    row.update({k: v for k, v in f.items() if k in _COLS})
    row["code"] = next_code()
    row["created_at"] = row["updated_at"] = now
    if pool.is_memory():
        row["id"] = pool.next_seq("grievance_id")
        _mem().append(row)
        return dict(row)
    cols = [c for c in _COLS if c != "id"]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO grievances ({', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id",
            [row[c] for c in cols],
        )
        row["id"] = cur.fetchone()[0]
        conn.commit()
    return dict(row)


def _get(where_sql, param):
    if pool.is_memory():
        key = where_sql
        return next((dict(g) for g in _mem() if g[key] == param), None)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM grievances WHERE {where_sql}=%s", (param,))
        r = cur.fetchone()
        return dict(zip(_COLS, r)) if r else None


def get_by_code(code: str):
    return _get("code", code)


def get_by_id(gid: int):
    return _get("id", gid)


def list_for_reporter(reporter_id: int):
    rows = _all()
    return sorted([g for g in rows if g["reporter_id"] == reporter_id],
                  key=lambda g: g["created_at"], reverse=True)


def _all():
    if pool.is_memory():
        return [dict(g) for g in _mem()]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM grievances")
        return [dict(zip(_COLS, r)) for r in cur.fetchall()]


def update(gid: int, **fields) -> dict:
    patch = {k: v for k, v in fields.items() if k in _COLS and k != "id"}
    patch["updated_at"] = time.time()
    if pool.is_memory():
        for g in _mem():
            if g["id"] == gid:
                g.update(patch)
                return dict(g)
        raise KeyError(gid)
    sets = ", ".join(f"{k}=%s" for k in patch)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE grievances SET {sets} WHERE id=%s", [*patch.values(), gid])
        conn.commit()
    return get_by_id(gid)


_SORTS = {
    "priority": lambda g: (-g["priority_score"], -g["created_at"]),
    "created":  lambda g: -g["created_at"],
    "due":      lambda g: (g["due_at"] or 9e18),
}


def list_query(*, status=None, category=None, responsible_unit=None, location_type=None,
               search=None, sort="priority", limit=200):
    rows = _all()
    if status:
        rows = [g for g in rows if g["status"] == status]
    if category:
        rows = [g for g in rows if g["category"] == category]
    if responsible_unit:
        rows = [g for g in rows if g["responsible_unit"] == responsible_unit]
    if location_type:
        rows = [g for g in rows if g["location_type"] == location_type]
    if search:
        s = search.lower()
        rows = [g for g in rows if s in (g["code"] or "").lower()
                or s in (g["description"] or "").lower()
                or s in (g["reporter_name"] or "").lower()]
    rows.sort(key=_SORTS.get(sort, _SORTS["priority"]))
    return rows[:limit]


def find_recurring_candidates(location_label: str, category: str, since_ts: float):
    return [g for g in _all()
            if g["location_label"] == location_label
            and g["category"] == category
            and g["status"] != "closed"
            and (g["created_at"] or 0) >= since_ts]
```

- [ ] **Step 5: Run both — pass.**

Run: `pytest tests/test_code_generator.py tests/test_grievances_db.py -q`

- [ ] **Step 6: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db/grievances.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_code_generator.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_grievances_db.py"
git commit -m "feat(unipulse): grievance persistence + code generator"
```

---

### Task 13: `db/evidence.py` + `db/timeline.py` + `db/audit.py`

**Files:**
- Create: `db/evidence.py`, `db/timeline.py`, `db/audit.py`
- Test: `tests/test_evidence_timeline_db.py`

**Interfaces:**
- `evidence.add(grievance_id, kind, *, image_url=None, image_key=None, thumbnail_url=None, note=None, uploaded_by) -> dict`
- `evidence.list_for(grievance_id) -> list[dict]` (oldest first)
- `evidence.has_kind(grievance_id, kind) -> bool`
- `timeline.add(grievance_id, event_type, *, from_value=None, to_value=None, actor, actor_role=None, note=None) -> dict`
- `timeline.list_for(grievance_id) -> list[dict]` (oldest first)
- `audit.add(actor, action, *, target_type=None, target_id=None, detail=None) -> dict`
- `audit.list_recent(limit=200) -> list[dict]` (newest first)

- [ ] **Step 1: Write `tests/test_evidence_timeline_db.py`**

```python
from db import audit, evidence, grievances, timeline, users
from services.auth_service import hash_pin


def _g(app):
    u = users.create("f", "F", "reporter", hash_pin("1"))
    return grievances.insert(reporter_id=u["id"], reporter_name="F", title="t",
                             description="a description here", location_type="hostels",
                             location_label="Hostels")


def test_evidence_roundtrip(app):
    g = _g(app)
    evidence.add(g["id"], "report", image_url="u1", uploaded_by="F")
    assert not evidence.has_kind(g["id"], "resolution_after")
    evidence.add(g["id"], "resolution_after", image_url="u2", note="fixed", uploaded_by="admin")
    assert evidence.has_kind(g["id"], "resolution_after")
    kinds = [e["kind"] for e in evidence.list_for(g["id"])]
    assert kinds == ["report", "resolution_after"]


def test_timeline_ordering(app):
    g = _g(app)
    timeline.add(g["id"], "created", actor="F", actor_role="reporter")
    timeline.add(g["id"], "status_change", from_value="reported", to_value="verified",
                 actor="admin", actor_role="admin")
    evs = timeline.list_for(g["id"])
    assert [e["event_type"] for e in evs] == ["created", "status_change"]
    assert evs[1]["to_value"] == "verified"


def test_audit_recent_newest_first(app):
    audit.add("admin", "user.create", target_type="user", target_id="7")
    audit.add("admin", "notice.publish", target_type="notice", target_id="2")
    recent = audit.list_recent()
    assert recent[0]["action"] == "notice.publish"
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Write the three modules** (same in-memory/Postgres dual pattern as `db/users.py`).

`db/evidence.py`:
```python
import time
from db import pool

_COLS = ("id", "grievance_id", "kind", "image_url", "image_key",
         "thumbnail_url", "note", "uploaded_by", "uploaded_at")


def _mem():
    return pool.STATE["mem"]["evidence"]


def add(grievance_id, kind, *, image_url=None, image_key=None, thumbnail_url=None,
        note=None, uploaded_by):
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("evidence"), "grievance_id": grievance_id, "kind": kind,
               "image_url": image_url, "image_key": image_key, "thumbnail_url": thumbnail_url,
               "note": note, "uploaded_by": uploaded_by, "uploaded_at": now}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO evidence (grievance_id, kind, image_url, image_key,
                                     thumbnail_url, note, uploaded_by, uploaded_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (grievance_id, kind, image_url, image_key, thumbnail_url, note, uploaded_by, now),
        )
        rid = cur.fetchone()[0]
        conn.commit()
    return {"id": rid, "grievance_id": grievance_id, "kind": kind, "image_url": image_url,
            "image_key": image_key, "thumbnail_url": thumbnail_url, "note": note,
            "uploaded_by": uploaded_by, "uploaded_at": now}


def list_for(grievance_id):
    if pool.is_memory():
        rows = [dict(e) for e in _mem() if e["grievance_id"] == grievance_id]
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLS)} FROM evidence WHERE grievance_id=%s", (grievance_id,))
            rows = [dict(zip(_COLS, r)) for r in cur.fetchall()]
    return sorted(rows, key=lambda e: e["uploaded_at"])


def has_kind(grievance_id, kind) -> bool:
    return any(e["kind"] == kind for e in list_for(grievance_id))
```

`db/timeline.py`:
```python
import time
from db import pool

_COLS = ("id", "grievance_id", "event_type", "from_value", "to_value",
         "actor", "actor_role", "note", "created_at")


def _mem():
    return pool.STATE["mem"]["timeline_events"]


def add(grievance_id, event_type, *, from_value=None, to_value=None, actor,
        actor_role=None, note=None):
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("timeline"), "grievance_id": grievance_id,
               "event_type": event_type, "from_value": from_value, "to_value": to_value,
               "actor": actor, "actor_role": actor_role, "note": note, "created_at": now}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO timeline_events (grievance_id, event_type, from_value, to_value,
                                            actor, actor_role, note, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (grievance_id, event_type, from_value, to_value, actor, actor_role, note, now),
        )
        rid = cur.fetchone()[0]
        conn.commit()
    return {"id": rid, "grievance_id": grievance_id, "event_type": event_type,
            "from_value": from_value, "to_value": to_value, "actor": actor,
            "actor_role": actor_role, "note": note, "created_at": now}


def list_for(grievance_id):
    if pool.is_memory():
        rows = [dict(e) for e in _mem() if e["grievance_id"] == grievance_id]
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLS)} FROM timeline_events WHERE grievance_id=%s",
                        (grievance_id,))
            rows = [dict(zip(_COLS, r)) for r in cur.fetchall()]
    return sorted(rows, key=lambda e: e["created_at"])
```

`db/audit.py`:
```python
import json
import time
from db import pool

_COLS = ("id", "actor", "action", "target_type", "target_id", "detail", "created_at")


def _mem():
    return pool.STATE["mem"]["audit_log"]


def add(actor, action, *, target_type=None, target_id=None, detail=None):
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("audit"), "actor": actor, "action": action,
               "target_type": target_type, "target_id": str(target_id) if target_id else None,
               "detail": detail or {}, "created_at": now}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log (actor, action, target_type, target_id, detail, created_at)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (actor, action, target_type, str(target_id) if target_id else None,
             json.dumps(detail or {}), now),
        )
        rid = cur.fetchone()[0]
        conn.commit()
    return {"id": rid, "actor": actor, "action": action, "target_type": target_type,
            "target_id": str(target_id) if target_id else None, "detail": detail or {},
            "created_at": now}


def list_recent(limit=200):
    if pool.is_memory():
        rows = [dict(e) for e in _mem()]
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLS)} FROM audit_log ORDER BY created_at DESC LIMIT %s",
                        (limit,))
            rows = [dict(zip(_COLS, r)) for r in cur.fetchall()]
    return sorted(rows, key=lambda e: e["created_at"], reverse=True)[:limit]
```

- [ ] **Step 4: Run — passes.** `pytest tests/test_evidence_timeline_db.py -q`

- [ ] **Step 5: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db/evidence.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/db/timeline.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/db/audit.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_evidence_timeline_db.py"
git commit -m "feat(unipulse): evidence, timeline, audit persistence"
```

---

### Task 14: `db/recurring.py` + `db/notices.py`

**Files:**
- Create: `db/recurring.py`, `db/notices.py`
- Test: `tests/test_recurring_db.py`, `tests/test_notices_db.py`

**Interfaces:**
- `recurring.find_active(location_label, category) -> dict | None`
- `recurring.create(location_label, category, title, primary_grievance_id, first_ts) -> dict` (status `active`, counts 0)
- `recurring.bump(group_id, *, last_ts, add_reporter: bool) -> dict` — `report_count += 1`, `reporter_count += (1 if add_reporter else 0)`, `last_reported_at = last_ts`
- `recurring.get(group_id) -> dict | None`
- `recurring.list_active() -> list[dict]`
- `recurring.set_status(group_id, status) -> dict`
- `notices.create(title, body, created_by, *, is_published=False, expires_at=None) -> dict`
- `notices.publish(nid, published: bool) -> dict`
- `notices.list_published(now: float | None = None) -> list[dict]` (drops expired; newest first)
- `notices.list_all() -> list[dict]`

- [ ] **Step 1: Write `tests/test_recurring_db.py`**

```python
from db import recurring


def test_create_find_bump(app):
    assert recurring.find_active("Hostels", "Plumbing") is None
    grp = recurring.create("Hostels", "Plumbing", "Hostels — Plumbing", 10, 100.0)
    assert grp["status"] == "active"
    assert recurring.find_active("Hostels", "Plumbing")["id"] == grp["id"]
    grp = recurring.bump(grp["id"], last_ts=200.0, add_reporter=True)
    grp = recurring.bump(grp["id"], last_ts=300.0, add_reporter=False)
    assert grp["report_count"] == 2
    assert grp["reporter_count"] == 1
    assert grp["last_reported_at"] == 300.0


def test_resolved_group_not_found_as_active(app):
    grp = recurring.create("Playground", "Civil", "t", 1, 1.0)
    recurring.set_status(grp["id"], "resolved")
    assert recurring.find_active("Playground", "Civil") is None
```

- [ ] **Step 2: Write `tests/test_notices_db.py`**

```python
from db import notices


def test_publish_and_list(app):
    n = notices.create("Water shutdown", "10am-2pm Block B", "admin")
    assert notices.list_published() == []
    notices.publish(n["id"], True)
    pub = notices.list_published()
    assert [x["title"] for x in pub] == ["Water shutdown"]


def test_expired_notice_excluded(app):
    n = notices.create("Old", "body", "admin", is_published=True, expires_at=50.0)
    assert notices.list_published(now=100.0) == []
    assert notices.list_published(now=10.0)[0]["id"] == n["id"]
```

- [ ] **Step 3: Run — fail.**

- [ ] **Step 4: Write `db/recurring.py`** and **`db/notices.py`** (dual memory/Postgres pattern; `find_active` filters `status='active'`; `list_published` filters `is_published AND (expires_at IS NULL OR expires_at > now)`).

```python
# db/recurring.py
import time
from db import pool

_COLS = ("id", "location_label", "category", "title", "report_count", "reporter_count",
         "first_reported_at", "last_reported_at", "status", "primary_grievance_id")


def _mem():
    return pool.STATE["mem"]["recurring_groups"]


def _all():
    if pool.is_memory():
        return [dict(x) for x in _mem()]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM recurring_groups")
        return [dict(zip(_COLS, r)) for r in cur.fetchall()]


def get(group_id):
    return next((g for g in _all() if g["id"] == group_id), None)


def find_active(location_label, category):
    return next((g for g in _all()
                 if g["location_label"] == location_label and g["category"] == category
                 and g["status"] == "active"), None)


def create(location_label, category, title, primary_grievance_id, first_ts):
    if pool.is_memory():
        row = {"id": pool.next_seq("recurring"), "location_label": location_label,
               "category": category, "title": title, "report_count": 0, "reporter_count": 0,
               "first_reported_at": first_ts, "last_reported_at": first_ts,
               "status": "active", "primary_grievance_id": primary_grievance_id}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO recurring_groups (location_label, category, title, report_count,
                    reporter_count, first_reported_at, last_reported_at, status, primary_grievance_id)
               VALUES (%s,%s,%s,0,0,%s,%s,'active',%s) RETURNING id""",
            (location_label, category, title, first_ts, first_ts, primary_grievance_id),
        )
        gid = cur.fetchone()[0]
        conn.commit()
    return get(gid)


def bump(group_id, *, last_ts, add_reporter):
    if pool.is_memory():
        for g in _mem():
            if g["id"] == group_id:
                g["report_count"] += 1
                g["reporter_count"] += 1 if add_reporter else 0
                g["last_reported_at"] = last_ts
                return dict(g)
        raise KeyError(group_id)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE recurring_groups
               SET report_count = report_count + 1,
                   reporter_count = reporter_count + %s,
                   last_reported_at = %s
               WHERE id = %s""",
            (1 if add_reporter else 0, last_ts, group_id),
        )
        conn.commit()
    return get(group_id)


def set_status(group_id, status):
    if pool.is_memory():
        for g in _mem():
            if g["id"] == group_id:
                g["status"] = status
                return dict(g)
        raise KeyError(group_id)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE recurring_groups SET status=%s WHERE id=%s", (status, group_id))
        conn.commit()
    return get(group_id)


def list_active():
    return [g for g in _all() if g["status"] == "active"]
```

```python
# db/notices.py
import time
from db import pool

_COLS = ("id", "title", "body", "audience", "created_by", "created_at",
         "is_published", "expires_at")


def _mem():
    return pool.STATE["mem"]["notices"]


def _all():
    if pool.is_memory():
        return [dict(x) for x in _mem()]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM notices")
        return [dict(zip(_COLS, r)) for r in cur.fetchall()]


def create(title, body, created_by, *, is_published=False, expires_at=None):
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("notice"), "title": title, "body": body, "audience": "all",
               "created_by": created_by, "created_at": now, "is_published": is_published,
               "expires_at": expires_at}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO notices (title, body, audience, created_by, created_at,
                                    is_published, expires_at)
               VALUES (%s,%s,'all',%s,%s,%s,%s) RETURNING id""",
            (title, body, created_by, now, is_published, expires_at),
        )
        nid = cur.fetchone()[0]
        conn.commit()
    return next(n for n in _all() if n["id"] == nid)


def publish(nid, published: bool):
    if pool.is_memory():
        for n in _mem():
            if n["id"] == nid:
                n["is_published"] = published
                return dict(n)
        raise KeyError(nid)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE notices SET is_published=%s WHERE id=%s", (published, nid))
        conn.commit()
    return next(n for n in _all() if n["id"] == nid)


def list_all():
    return sorted(_all(), key=lambda n: n["created_at"], reverse=True)


def list_published(now: float | None = None):
    now = time.time() if now is None else now
    out = [n for n in _all() if n["is_published"]
           and (n["expires_at"] is None or n["expires_at"] > now)]
    return sorted(out, key=lambda n: n["created_at"], reverse=True)
```

- [ ] **Step 5: Run — pass.** `pytest tests/test_recurring_db.py tests/test_notices_db.py -q`

- [ ] **Step 6: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db/recurring.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/db/notices.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_recurring_db.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_notices_db.py"
git commit -m "feat(unipulse): recurring groups + notices persistence"
```

---

### Task 15: `db/seeds.py` + wire into startup

**Files:**
- Create: `db/seeds.py`
- Test: `tests/test_seeds.py`; un-skip `tests/test_boot.py`

**Interfaces:**
- Consumes: `users.create/get_by_username`, `locations.seed`, `notices.create`, `auth_service.hash_pin`.
- Produces: `seeds.run() -> None` — idempotent. Ensures: 1 admin (`admin`/`0000`), 4 demo faculty (`prof.sharma`, `prof.rao`, `dr.iyer`, `prof.khan` — all PIN `1234`, departments set), locations seeded, 2 published demo notices. Skips any that already exist.
- Produces: `seeds.DEMO_FACULTY: list[tuple]` for reuse in later phases' demo-data script.

- [ ] **Step 1: Write `tests/test_seeds.py`**

```python
from db import seeds, users, locations, notices


def test_seed_creates_admin_and_faculty(app):
    seeds.run()
    admin = users.get_by_username("admin")
    assert admin and admin["role"] == "admin"
    assert len(users.list_all(role="reporter")) >= 4


def test_seed_is_idempotent(app):
    seeds.run()
    seeds.run()
    assert len(users.list_all()) == 1 + len(seeds.DEMO_FACULTY)
    assert len(notices.list_published()) == 2


def test_admin_pin_is_0000(app):
    seeds.run()
    from services.auth_service import verify_pin
    assert verify_pin("0000", users.get_by_username("admin")["pin_hash"])
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Write `db/seeds.py`**

```python
"""Idempotent seed data: admin, demo faculty, locations, demo notices."""
from db import locations, notices, users
from services.auth_service import hash_pin

DEMO_FACULTY = [
    ("prof.sharma", "Prof. Anil Sharma",  "Mechanical Engineering"),
    ("prof.rao",    "Prof. Meera Rao",    "Computer Science"),
    ("dr.iyer",     "Dr. Karthik Iyer",   "Electronics & Communication"),
    ("prof.khan",   "Prof. Sadiya Khan",  "Civil Engineering"),
]


def run() -> None:
    if not users.get_by_username("admin"):
        users.create("admin", "Campus Super Admin", "admin", hash_pin("0000"),
                     department="Campus Infrastructure Office", created_by="seed")
    for uname, name, dept in DEMO_FACULTY:
        if not users.get_by_username(uname):
            users.create(uname, name, "reporter", hash_pin("1234"),
                         department=dept, created_by="seed")

    locations.seed()

    if not notices.list_all():
        n1 = notices.create(
            "Water supply maintenance — Block B",
            "Water will be shut off in Academics Block B on Saturday 9:00-13:00 for tank cleaning.",
            "seed", is_published=True)
        n2 = notices.create(
            "Report campus issues on UniPulse",
            "Faculty can now report infrastructure problems (electrical, plumbing, IT, civil, "
            "mechanical, power) from their phone. Tap 'Report an Issue' on the home screen.",
            "seed", is_published=True)
```

- [ ] **Step 4: Replace the placeholder in `tests/test_boot.py`** with the real content from Task 6 Step 4 (already written) and remove any `@pytest.mark.skip`.

- [ ] **Step 5: Run the whole suite**

Run: `pytest -q`
Expected: ALL PASS.

- [ ] **Step 6: Manual boot check**

Run: `python -c "from app import create_app; c=create_app().test_client(); r=c.get('/healthz'); print(r.get_json())"`
Expected: `{'ok': True, 'db': 'memory'}`

Run a login round-trip:
```bash
python -c "
from app import create_app
c = create_app().test_client()
r = c.post('/login', data={'username':'admin','pin':'0000'})
print('login', r.status_code, r.headers.get('Location'))
assert r.status_code == 302 and r.headers['Location'].endswith('/admin')
bad = c.post('/login', data={'username':'admin','pin':'9999'})
print('bad pin', bad.status_code)
assert bad.status_code == 401
print('OK')
"
```

- [ ] **Step 7: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/db/seeds.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_seeds.py" \
        "OneDrive/Desktop/unipulse/unipulse-campus/tests/test_boot.py"
git commit -m "feat(unipulse): startup seeds (admin, demo faculty, locations, notices)"
```

---

### Task 16: `Procfile` + `.env.example` + `PHASE1_NOTES.md` update + green suite

**Files:**
- Modify: `Procfile`
- Create: `.env.example`
- Modify: `PHASE1_NOTES.md` (append a "superseded" pointer to the design spec)

- [ ] **Step 1: Write `Procfile`**

```
web: gunicorn wsgi:app --workers 2 --timeout 60 --bind 0.0.0.0:$PORT
```

- [ ] **Step 2: Write `.env.example`**

```
# Leave DATABASE_URL empty to run fully in-memory (data lost on restart).
DATABASE_URL=
SECRET_KEY=
JWT_SECRET=
APP_ENV=development
# Optional — features degrade gracefully when unset:
GROQ_API_KEY=
RESEND_API_KEY=
IMAGEKIT_PRIVATE_KEY=
```

- [ ] **Step 3: Append to `PHASE1_NOTES.md`**

```markdown

---
**Superseded 2026-08-30.** The project was re-scoped to the full campus MVP. See
`docs/superpowers/specs/2026-08-30-unipulse-campus-design.md` and the plans under
`docs/superpowers/plans/`. Phase-0+A restructured this fork into an app-factory
layout; the NGO/role/location work from this note still holds.
```

- [ ] **Step 4: Full green run + lint-ish check**

Run: `pytest -q`
Expected: all pass.

Run: `python -m compileall -q app.py wsgi.py config.py db domain services blueprints`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add "OneDrive/Desktop/unipulse/unipulse-campus/Procfile" \
        "OneDrive/Desktop/unipulse/unipulse-campus/.env.example" \
        "OneDrive/Desktop/unipulse/unipulse-campus/PHASE1_NOTES.md"
git commit -m "chore(unipulse): deploy config + phase-0/A wrap-up"
```

---

## Self-Review

**Spec coverage (Phase 0 + A scope only):**
- §3 layout → Tasks 1, 3, 5 (app factory, `db/`, blueprints scaffold). ✅
- §4 every table → Task 9 DDL + Tasks 10-14 per-entity modules. ✅
- §5 constants → Task 6. ✅
- §6 RBAC → Task 8. ✅
- §7 auth (JWT cookies, rate-limit, no session) → Tasks 4, 5. ✅
- §7 seeds (admin + demo faculty) → Task 15. ✅
- Location master data incl. Academics drill-down → Task 11. ✅
- Grievance code generator → Task 12. ✅
- Recurring-detection *data* (groups table + candidate query + key helper) → Tasks 7, 12, 14 (the *service* that uses them is Phase B). ✅
- Deferred to later phases (correctly not here): faculty/admin blueprints & templates (B/C), `ai/engine.py` (B), `grievance_service` pipeline (B), priority formula (D), pulse/gaps (D), Resend (E). ✅

**Placeholder scan:** no "TBD/TODO/handle edge cases"; every code step has full code; every test step has full test code. ✅

**Type consistency:**
- `users.create(...) -> dict` shape `{id, username, display_name, role, pin_hash, department, contact, is_active, created_at, created_by}` — used consistently in Tasks 4 (`login`), 10, 15.
- `grievances.insert(**)` required keys `reporter_id, reporter_name, title, description, location_type, location_label` — matches Task 12 tests and `find_recurring_candidates` usage.
- `recurring.create(location_label, category, title, primary_grievance_id, first_ts)` / `.bump(group_id, *, last_ts, add_reporter)` — consistent Task 14 signatures & tests.
- `auth_service.login` returns `LoginResult` with `.user` (dict), `.access_token`, `.refresh_token`, `.success`, `.error` — used in Task 5 blueprint.
- Cookie names `up_access` / `up_refresh` — consistent Tasks 4/5 (Task 4 doesn't name cookies; Task 5 owns them). ✅
- `pool.STATE` keys `mode / pg_pool / mem / seq` — consistent across all `db/` modules. ✅

No issues found.
