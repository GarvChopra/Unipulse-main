"""Campus location master data + picker queries."""
from db import pool
from domain.constants import (ACADEMICS_BLOCKS, ACADEMICS_FLOORS, LOCATION_TYPES,
                              OUTER_AREA_SUBZONES)

_COLS = ("id", "parent_id", "location_type", "name", "full_path", "is_active")


def _mem():
    return pool.STATE["mem"]["locations"]


def _seed_rows():
    rows = []
    for t in LOCATION_TYPES:
        rows.append(("type", t["name"], t["name"]))
    for z in OUTER_AREA_SUBZONES:
        rows.append(("subzone", z, f"Outer Area > {z}"))
    for b in ACADEMICS_BLOCKS:
        rows.append(("block", b, f"Academics Block > {b}"))
    for f in ACADEMICS_FLOORS:
        rows.append(("floor", f, f"Academics Block > {f}"))
    return [{"location_type": lt, "name": nm, "full_path": fp} for (lt, nm, fp) in rows]


def seed() -> None:
    for r in _seed_rows():
        if _get_by_path(r["full_path"]) is None:
            create(r["location_type"], r["name"], r["full_path"])


def _get_by_path(full_path):
    if pool.is_memory():
        return next((dict(l) for l in _mem() if l["full_path"] == full_path), None)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM locations WHERE full_path=%s", (full_path,))
        r = cur.fetchone()
        return dict(zip(_COLS, r)) if r else None


def create(location_type, name, full_path, parent_id=None):
    if _get_by_path(full_path):
        raise ValueError(f"location {full_path!r} exists")
    if pool.is_memory():
        row = {"id": pool.next_seq("locations"), "parent_id": parent_id,
               "location_type": location_type, "name": name, "full_path": full_path,
               "is_active": True}
        _mem().append(row)
        return dict(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO locations (parent_id, location_type, name, full_path, is_active)
               VALUES (%s,%s,%s,%s,TRUE) RETURNING id""",
            (parent_id, location_type, name, full_path),
        )
        cur.fetchone()
        conn.commit()
    return _get_by_path(full_path)


def list_all(active_only=True):
    if pool.is_memory():
        rows = [dict(l) for l in _mem()]
    else:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COLS)} FROM locations ORDER BY full_path")
            rows = [dict(zip(_COLS, r)) for r in cur.fetchall()]
    return [r for r in rows if r["is_active"] or not active_only]


def set_active(loc_id, active) -> None:
    if pool.is_memory():
        for l in _mem():
            if l["id"] == loc_id:
                l["is_active"] = active
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE locations SET is_active=%s WHERE id=%s", (active, loc_id))
        conn.commit()


def picker() -> dict:
    active = list_all()
    blocks = [l["name"] for l in active if l["location_type"] == "block"] or list(ACADEMICS_BLOCKS)
    floors = [l["name"] for l in active if l["location_type"] == "floor"] or list(ACADEMICS_FLOORS)
    subs = [l["name"] for l in active if l["location_type"] == "subzone"] or list(OUTER_AREA_SUBZONES)
    return {"types": LOCATION_TYPES, "outer_area_subzones": subs,
            "academics_blocks": blocks, "academics_floors": floors}
