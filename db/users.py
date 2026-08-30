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
