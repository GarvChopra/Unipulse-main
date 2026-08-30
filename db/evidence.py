"""Evidence (photos + notes) persistence."""
import time

from db import pool

_COLS = ("id", "grievance_id", "kind", "image_url", "image_key",
         "thumbnail_url", "note", "uploaded_by", "uploaded_at")


def _mem():
    return pool.STATE["mem"]["evidence"]


def add(grievance_id, kind, *, image_url=None, image_key=None, thumbnail_url=None,
        note=None, uploaded_by):
    now = time.time()
    if pool.is_memory():
        row = {"id": pool.next_seq("evidence"), "grievance_id": grievance_id, "kind": kind,
               "image_url": image_url, "image_key": image_key, "thumbnail_url": thumbnail_url,
               "note": note, "uploaded_by": uploaded_by, "uploaded_at": now}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO evidence (grievance_id, kind, image_url, image_key,
                                     thumbnail_url, note, uploaded_by, uploaded_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (grievance_id, kind, image_url, image_key, thumbnail_url, note, uploaded_by, now),
        )
        rid = cur.fetchone()[0]
        conn.commit()
    return {"id": rid, "grievance_id": grievance_id, "kind": kind, "image_url": image_url,
            "image_key": image_key, "thumbnail_url": thumbnail_url, "note": note,
            "uploaded_by": uploaded_by, "uploaded_at": now}


def list_for(grievance_id):
    if pool.is_memory():
        rows = [dict(e) for e in _mem() if e["grievance_id"] == grievance_id]
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLS)} FROM evidence WHERE grievance_id=%s",
                        (grievance_id,))
            rows = [dict(zip(_COLS, r)) for r in cur.fetchall()]
    return sorted(rows, key=lambda e: (e["uploaded_at"], e["id"]))


def has_kind(grievance_id, kind) -> bool:
    return any(e["kind"] == kind for e in list_for(grievance_id))
