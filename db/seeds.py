"""Idempotent seed data: admin, demo faculty, locations, demo notices,
plus the richer demo grievance dataset (recurring issue + gaps)."""
from db import locations, notices, pool, users
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
        notices.create(
            "Water supply maintenance - Block B",
            "Water will be shut off in Academics Block B on Saturday 9:00-13:00 for tank cleaning.",
            "seed", is_published=True)
        notices.create(
            "Report campus issues on UniPulse",
            "Faculty can now report infrastructure problems (electrical, plumbing, IT, civil, "
            "mechanical, power) from their phone. Tap 'Report an Issue' on the home screen.",
            "seed", is_published=True)

    # Richer demo dataset (sample grievances, the recurring "Room 204" issue,
    # Block B infrastructure gaps) — scripts/seed_demo.py's build() is already
    # idempotent (it checks for existing grievances and no-ops if any exist),
    # so it's safe to call on every boot. Wrapped defensively: if anything in
    # that script errors (e.g. a dependency it needs isn't available in this
    # environment), it's logged and skipped rather than crashing app startup.
    try:
        from scripts.seed_demo import build as _build_demo_grievances
        result = _build_demo_grievances()
        print(f"[seeds] demo grievance dataset: {result}")
    except Exception as e:  # noqa: BLE001
        print(f"[seeds] demo grievance seed skipped: {type(e).__name__}: {e}")

    # Firestore mode only loads from Firestore at boot — it never writes back on
    # its own. Since run() executes automatically on every startup (see app.py),
    # flushing here is what actually makes all of the above show up as real
    # Firestore documents instead of only living in this process's memory.
    if pool.is_firestore():
        pool.flush_to_firestore()
