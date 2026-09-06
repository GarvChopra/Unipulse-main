"""Startup seeding.

Split into three concerns:

* `seed_essential()` — real campus structure (locations). Always runs, every
  environment. Idempotent.
* `_bootstrap_admin()` — the first coordinator account. In production this comes
  ONLY from INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PIN; there is no automatic
  admin/0000. Development keeps admin/0000 for convenience.
* `seed_demo()` — demo faculty accounts, demo notices and (opt-in) the ~35 fake
  demo grievances. Never runs against a production database unless
  ALLOW_PROD_DEMO_SEED=1 is explicitly set.

`run()` wires them together and is what `create_app()` calls.
"""
import logging
import os

from config import Config
from db import locations, notices, pool, users
from services.auth_service import hash_pin

log = logging.getLogger("unifix.seeds")

DEMO_FACULTY = [
    ("prof.sharma", "Prof. Anil Sharma",  "Mechanical Engineering"),
    ("prof.rao",    "Prof. Meera Rao",    "Computer Science"),
    ("dr.iyer",     "Dr. Karthik Iyer",   "Electronics & Communication"),
    ("prof.khan",   "Prof. Sadiya Khan",  "Civil Engineering"),
]

_DEV_ADMIN_USER = "admin"
_DEV_ADMIN_PIN = "0000"


def seed_essential() -> None:
    """Real data every environment needs. Idempotent."""
    locations.seed()


def _bootstrap_admin() -> None:
    if users.list_all(role="admin"):
        return

    cfg_user = Config.INITIAL_ADMIN_USERNAME
    cfg_pin = Config.INITIAL_ADMIN_PIN
    if cfg_user and cfg_pin:
        users.create(cfg_user, "Campus Super Admin", "admin", hash_pin(cfg_pin),
                     department="Campus Infrastructure Office", created_by="bootstrap",
                     must_change_pin=True)
        log.info("bootstrapped initial admin %r from INITIAL_ADMIN_* env "
                 "(must change PIN on first login)", cfg_user)
        return

    if Config.is_production():
        raise RuntimeError(
            "UNIFIX cannot start: no admin account exists and no initial admin "
            "is configured. Set INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PIN in "
            "the environment and redeploy."
        )

    users.create(_DEV_ADMIN_USER, "Campus Super Admin", "admin",
                 hash_pin(_DEV_ADMIN_PIN),
                 department="Campus Infrastructure Office", created_by="seed")
    log.warning("created development admin %r / PIN %r — DEV ONLY, never in production",
                _DEV_ADMIN_USER, _DEV_ADMIN_PIN)


def _demo_allowed() -> bool:
    if not Config.is_production():
        return True
    if Config.ALLOW_PROD_DEMO_SEED:
        log.warning("ALLOW_PROD_DEMO_SEED=1 — seeding DEMO data into a PRODUCTION "
                    "database. This is almost never what you want.")
        return True
    return False


def seed_demo() -> None:
    """Demo faculty + notices + (opt-in) demo grievances. Skipped in production
    unless explicitly overridden."""
    if not _demo_allowed():
        log.info("production: demo data seeding skipped")
        return

    for uname, name, dept in DEMO_FACULTY:
        if not users.get_by_username(uname):
            users.create(uname, name, "reporter", hash_pin("1234"),
                         department=dept, created_by="seed")

    if not notices.list_all():
        notices.create(
            "Water supply maintenance - Block B",
            "Water will be shut off in Academics Block B on Saturday 9:00-13:00 for tank cleaning.",
            "seed", is_published=True)
        notices.create(
            "Report campus issues on UNIFIX",
            "Employees can now report infrastructure problems (electrical, plumbing, IT, civil, "
            "mechanical, power) from their phone. Tap 'Report an Issue' on the home screen.",
            "seed", is_published=True)

    # Richer demo dataset (sample grievances, the recurring "Room 204" issue,
    # Block B infrastructure gaps). Still opt-in via SEED_DEMO=1: it injects ~35
    # fake grievances and breaks tests that assume an empty store. build() is
    # idempotent and wrapped so a failure never crashes startup.
    if os.environ.get("SEED_DEMO") == "1":
        try:
            from scripts.seed_demo import build as _build_demo_grievances
            result = _build_demo_grievances()
            log.info("demo grievance dataset: %s", result)
        except Exception as e:  # noqa: BLE001
            log.warning("demo grievance seed skipped: %s: %s", type(e).__name__, e)


def run() -> None:
    seed_essential()
    _bootstrap_admin()
    seed_demo()

    # Firestore mode only loads from Firestore at boot — it never writes back on
    # its own. run() executes on every startup, so flushing here is what makes
    # the seeded rows real Firestore documents instead of process-local memory.
    if pool.is_firestore():
        pool.flush_to_firestore()
