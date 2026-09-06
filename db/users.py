"""User account persistence (faculty + admin)."""
import time

from db import pool

_COLS = ("id", "username", "display_name", "role", "pin_hash",
         "department", "contact", "is_active", "created_at", "created_by",
         "must_change_pin", "deletion_requested")

VALID_ROLES = ("reporter", "admin")


def _mem():
    return pool.STATE["mem"]["users"]


def _row(d: dict) -> dict:
    r = {k: d.get(k) for k in _COLS}
    r["must_change_pin"] = bool(r.get("must_change_pin"))
    r["deletion_requested"] = bool(r.get("deletion_requested"))
    return r


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


def count_active_admins() -> int:
    return sum(1 for u in list_all(role="admin") if u.get("is_active", True))


def create(username, display_name, role, pin_hash, department=None, contact=None,
           created_by=None, must_change_pin=False):
    username = username.lower().strip()
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role {role!r}")
    if get_by_username(username):
        raise ValueError(f"username {username!r} already exists")
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("users"), "username": username, "display_name": display_name,
               "role": role, "pin_hash": pin_hash, "department": department, "contact": contact,
               "is_active": True, "created_at": now, "created_by": created_by,
               "must_change_pin": bool(must_change_pin)}
        _mem().append(row)
        return _row(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO users (username, display_name, role, pin_hash, department,
                                  contact, is_active, created_at, created_by, must_change_pin)
               VALUES (%s,%s,%s,%s,%s,%s,TRUE,%s,%s,%s) RETURNING id""",
            (username, display_name, role, pin_hash, department, contact, now, created_by,
             bool(must_change_pin)),
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
    """Set a new PIN. Always clears must_change_pin — the user just chose one."""
    if pool.is_memory():
        for u in _mem():
            if u["id"] == uid:
                u["pin_hash"] = pin_hash
                u["must_change_pin"] = False
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET pin_hash=%s, must_change_pin=FALSE WHERE id=%s",
                    (pin_hash, uid))
        conn.commit()


def set_must_change_pin(uid: int, flag: bool) -> None:
    if pool.is_memory():
        for u in _mem():
            if u["id"] == uid:
                u["must_change_pin"] = bool(flag)
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET must_change_pin=%s WHERE id=%s", (bool(flag), uid))
        conn.commit()


def request_deletion(uid: int) -> None:
    """User asked for account + data deletion (Google Play requirement).
    Deactivates the login and flags it for the administrator to finish."""
    if pool.is_memory():
        for u in _mem():
            if u["id"] == uid:
                u["deletion_requested"] = True
                u["is_active"] = False
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET deletion_requested=TRUE, is_active=FALSE WHERE id=%s",
                    (uid,))
        conn.commit()


def deidentify(uid: int) -> None:
    """Administrator completes a deletion request: strip personal data, keep the
    row so historical grievances still resolve to a (now anonymous) reporter."""
    fields = dict(display_name="Former staff", department=None, contact=None,
                  pin_hash="", is_active=False, deletion_requested=False,
                  username=f"deleted-{uid}")
    if pool.is_memory():
        for u in _mem():
            if u["id"] == uid:
                u.update(fields)
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE users SET display_name=%s, department=NULL, contact=NULL,
                       pin_hash='', is_active=FALSE, deletion_requested=FALSE, username=%s
                   WHERE id=%s""",
                (fields["display_name"], fields["username"], uid))
            conn.commit()

    # de-identify the denormalised reporter name on their grievances (both modes)
    from db import grievances
    for g in grievances.list_query(limit=100000):
        if g["reporter_id"] == uid:
            grievances.update(g["id"], reporter_name="Former staff")


def list_deletion_requests():
    return [u for u in list_all() if u.get("deletion_requested")]
