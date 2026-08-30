"""Campus notice persistence."""
import time

from db import pool

_COLS = ("id", "title", "body", "audience", "created_by", "created_at",
         "is_published", "expires_at")


def _mem():
    return pool.STATE["mem"]["notices"]


def _all():
    if pool.is_memory():
        return [dict(x) for x in _mem()]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM notices")
        return [dict(zip(_COLS, r)) for r in cur.fetchall()]


def get(nid):
    return next((n for n in _all() if n["id"] == nid), None)


def create(title, body, created_by, *, is_published=False, expires_at=None):
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("notice"), "title": title, "body": body, "audience": "all",
               "created_by": created_by, "created_at": now, "is_published": is_published,
               "expires_at": expires_at}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO notices (title, body, audience, created_by, created_at,
                                    is_published, expires_at)
               VALUES (%s,%s,'all',%s,%s,%s,%s) RETURNING id""",
            (title, body, created_by, now, is_published, expires_at),
        )
        nid = cur.fetchone()[0]
        conn.commit()
    return get(nid)


def publish(nid, published: bool):
    if pool.is_memory():
        for n in _mem():
            if n["id"] == nid:
                n["is_published"] = published
                return dict(n)
        raise KeyError(nid)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE notices SET is_published=%s WHERE id=%s", (published, nid))
        conn.commit()
    return get(nid)


def update(nid, **fields):
    patch = {k: v for k, v in fields.items() if k in _COLS and k not in ("id", "created_at")}
    if pool.is_memory():
        for n in _mem():
            if n["id"] == nid:
                n.update(patch)
                return dict(n)
        raise KeyError(nid)
    sets = ", ".join(f"{k}=%s" for k in patch)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE notices SET {sets} WHERE id=%s", [*patch.values(), nid])
        conn.commit()
    return get(nid)


def list_all():
    return sorted(_all(), key=lambda n: (n["created_at"], n["id"]), reverse=True)


def list_published(now: float | None = None):
    now = time.time() if now is None else now
    out = [n for n in _all() if n["is_published"]
           and (n["expires_at"] is None or n["expires_at"] > now)]
    return sorted(out, key=lambda n: (n["created_at"], n["id"]), reverse=True)
