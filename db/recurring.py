"""Recurring-issue group persistence."""
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


def list_active():
    return sorted([g for g in _all() if g["status"] == "active"],
                  key=lambda g: g["last_reported_at"] or 0, reverse=True)


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


def members(group_id):
    from db import grievances
    return [g for g in grievances.list_query(limit=100000)
            if g.get("recurring_group_id") == group_id]


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
