"""Persistence backend: PostgreSQL primary, in-memory fallback. Same dict shapes both ways."""
import time
from contextlib import contextmanager

from config import Config

_PG_OK = False
try:
    import psycopg  # noqa: F401
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
                cur.execute("CREATE SEQUENCE IF NOT EXISTS seq_%s" % name)
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
