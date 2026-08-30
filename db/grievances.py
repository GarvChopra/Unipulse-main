"""Grievance persistence: code generation, CRUD, queries."""
import time

from db import pool
from domain.constants import CODE_PAD, CODE_PREFIX

_COLS = (
    "id", "code", "reporter_id", "reporter_name", "title", "description", "category",
    "category_confirmed", "severity", "priority_score", "status", "location_type",
    "block_no", "floor", "room", "sub_zone", "location_label", "responsible_unit",
    "assignee", "assigned_at", "due_at", "recurring_group_id", "ai_summary",
    "ai_confidence", "spam_flag", "noticed_at", "affects_academics",
    "primary_photo_url", "thumbnail_url",
    "created_at", "updated_at", "resolved_at", "closed_at",
)
_DEFAULTS = {
    "category": None, "category_confirmed": False, "severity": None, "priority_score": 0,
    "status": "reported", "block_no": None, "floor": None, "room": None, "sub_zone": None,
    "responsible_unit": None, "assignee": None, "assigned_at": None, "due_at": None,
    "recurring_group_id": None, "ai_summary": None, "ai_confidence": None, "spam_flag": False,
    "noticed_at": None, "affects_academics": False,
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


def _get(where_col, param):
    if pool.is_memory():
        return next((dict(g) for g in _mem() if g[where_col] == param), None)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM grievances WHERE {where_col}=%s", (param,))
        r = cur.fetchone()
        return dict(zip(_COLS, r)) if r else None


def get_by_code(code: str):
    return _get("code", code)


def get_by_id(gid: int):
    return _get("id", gid)


def _all():
    if pool.is_memory():
        return [dict(g) for g in _mem()]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM grievances")
        return [dict(zip(_COLS, r)) for r in cur.fetchall()]


def list_for_reporter(reporter_id: int):
    return sorted([g for g in _all() if g["reporter_id"] == reporter_id],
                  key=lambda g: (g["created_at"], g["id"]), reverse=True)


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
    "priority": lambda g: (-(g["priority_score"] or 0), -(g["created_at"] or 0)),
    "created":  lambda g: -(g["created_at"] or 0),
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
