"""Persistence backend: Firestore > PostgreSQL > in-memory. Same dict shapes throughout.

Firestore mode reuses the exact in-memory code path in every db/*.py module
(users.py, grievances.py, locations.py, evidence.py, timeline.py, audit.py,
recurring.py, notices.py all branch on pool.is_memory() already) — those files
are untouched. Firestore just loads its collections into STATE["mem"] at boot
and flush_to_firestore() writes the snapshot back.
"""
import base64
import json
import os
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

_FS_OK = False
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    _FS_OK = True
except ImportError:
    firebase_admin = None
    firestore = None

_MEM_TABLES = (
    "users", "locations", "grievances", "evidence",
    "timeline_events", "recurring_groups", "notices", "audit_log",
)

# table name -> the next_seq() name each db/*.py module actually uses for "id"
_ID_SEQ_NAME = {
    "users": "users",
    "locations": "locations",
    "grievances": "grievance_id",   # note: separate from the "grievance" code sequence
    "evidence": "evidence",
    "timeline_events": "timeline",
    "recurring_groups": "recurring",
    "notices": "notice",
    "audit_log": "audit",
}

STATE = {"mode": "memory", "pg_pool": None, "mem": {}, "seq": {}, "firestore_db": None}


def reset_memory_store() -> None:
    STATE["mode"] = "memory"
    STATE["pg_pool"] = None
    STATE["mem"] = {t: [] for t in _MEM_TABLES}
    STATE["seq"] = {}


def is_memory() -> bool:
    # Firestore mode is a durable variant of memory mode — same STATE["mem"] shape,
    # so every db/*.py module's existing memory branch works unchanged.
    return STATE["mode"] in ("memory", "firestore")


def is_firestore() -> bool:
    return STATE["mode"] == "firestore"


@contextmanager
def connection():
    if STATE["mode"] != "postgres" or not STATE["pg_pool"]:
        raise RuntimeError("pool.connection() called outside postgres mode")
    with STATE["pg_pool"].connection() as conn:
        yield conn


def next_seq(name: str) -> int:
    if STATE["mode"] == "postgres":
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE SEQUENCE IF NOT EXISTS seq_%s" % name)
                cur.execute("SELECT nextval(%s)", (f"seq_{name}",))
                val = cur.fetchone()[0]
            conn.commit()
            return int(val)
    STATE["seq"][name] = STATE["seq"].get(name, 0) + 1
    return STATE["seq"][name]


# ---------------------------------------------------------------- Firestore --

def _init_firestore():
    """Returns a firestore client, or None if not configured / not installed."""
    # "".join(...split()) strips ALL whitespace, including newlines that can get
    # embedded when a long base64 string is copy-pasted through a terminal or a
    # web form's textarea — plain .strip() only catches the two ends, which is
    # not enough if a line-wrap introduced a newline in the middle of the string.
    b64 = "".join(os.environ.get("FIREBASE_CREDENTIALS_B64", "").split())
    if not b64 or not _FS_OK:
        return None
    try:
        raw = base64.b64decode(b64)
        cred_dict = json.loads(raw)
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:  # noqa: BLE001
        print(f"[db] Firestore init failed: {type(e).__name__}: {e}")
        return None


def _firestore_load(db) -> None:
    """Pull every collection from Firestore into STATE['mem']."""
    for table in _MEM_TABLES:
        try:
            docs = db.collection(table).stream()
            STATE["mem"][table] = [d.to_dict() for d in docs]
        except Exception as e:  # noqa: BLE001
            print(f"[db] Firestore load '{table}' failed: {type(e).__name__}: {e}")
            STATE["mem"][table] = []


def _restore_sequences() -> None:
    """After loading existing data, make sure next_seq() won't hand out an id
    that already exists in the loaded rows."""
    for table, seq_name in _ID_SEQ_NAME.items():
        ids = [r.get("id") for r in STATE["mem"].get(table, []) if isinstance(r.get("id"), int)]
        if ids:
            STATE["seq"][seq_name] = max(STATE["seq"].get(seq_name, 0), max(ids))

    # grievances also has a separate "grievance" sequence that drives the
    # human-readable code (e.g. AP-CAMP-00124) — recover it from existing codes.
    nums = []
    for row in STATE["mem"].get("grievances", []):
        digits = "".join(ch for ch in str(row.get("code", "")) if ch.isdigit())
        if digits:
            nums.append(int(digits))
    if nums:
        STATE["seq"]["grievance"] = max(STATE["seq"].get("grievance", 0), max(nums))


def flush_to_firestore() -> None:
    """Write the current in-memory snapshot back to Firestore. Call this after
    seeding, and ideally after requests that write data (see app.py note)."""
    db = STATE.get("firestore_db")
    if not db:
        return
    for table in _MEM_TABLES:
        col = db.collection(table)
        for row in STATE["mem"].get(table, []):
            doc_id = str(row.get("id"))
            if doc_id and doc_id != "None":
                col.document(doc_id).set(row, merge=False)


# --------------------------------------------------------------------- init --

def init_db() -> None:
    from db import schema

    reset_memory_store()

    # 1) Firestore first, per current config — durable, no Postgres needed.
    fs_db = _init_firestore()
    if fs_db:
        STATE["firestore_db"] = fs_db
        STATE["mode"] = "firestore"
        _firestore_load(fs_db)
        _restore_sequences()
        print("[db] Firestore connected — loaded into memory-backed store")
        return

    # 2) Postgres, unchanged from before — only reached if Firestore isn't configured.
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

    # 3) Nothing configured — plain in-memory, data lost on restart.
    STATE["mode"] = "memory"
