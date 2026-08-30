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
        notices.create(
            "Water supply maintenance - Block B",
            "Water will be shut off in Academics Block B on Saturday 9:00-13:00 for tank cleaning.",
            "seed", is_published=True)
        notices.create(
            "Report campus issues on UniPulse",
            "Faculty can now report infrastructure problems (electrical, plumbing, IT, civil, "
            "mechanical, power) from their phone. Tap 'Report an Issue' on the home screen.",
            "seed", is_published=True)
