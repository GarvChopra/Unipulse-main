"""Per-grievance timeline events (also the grievance-scoped audit trail)."""
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
    return sorted(rows, key=lambda e: (e["created_at"], e["id"]))
