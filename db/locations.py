"""Campus location tree + picker / denormalization helpers.

Shape
-----
    campus
      ├── building (AB1, AB2)            bucket = academics_block
      │     └── floor                    bucket = academics_block
      │           └── room  (+room_type) bucket = academics_block
      ├── facility (Library, SHD Hall…)  bucket = facility
      │     └── area  ("specific area")
      ├── facility (B.Tech/MBA/BCA Canteen)   bucket = mess_canteen
      ├── facility (Hostels)             bucket = hostels
      ├── facility (Playground)          bucket = playground
      └── zone (Outer Area)              bucket = outer_area
            └── subzone (Security…)      bucket = outer_area

`bucket` is the coarse `location_type` copied onto the grievance row so the
intelligence layer, validation and duplicate detection keep working unchanged.
Rooms are NEVER seeded — the admin adds the real GL Bajaj room list later.
"""
from db import pool
from domain.constants import (BUILDING_FLOORS, CAMPUS_BUILDINGS, CAMPUS_CANTEENS,
                              CAMPUS_FACILITIES, CAMPUS_NAME, OUTER_AREA_SUBZONES)

_COLS = ("id", "parent_id", "location_type", "name", "full_path", "is_active",
         "room_type", "bucket", "sort_order")

# node kinds that a reporter can file an issue against directly
PICKABLE = ("building", "floor", "room", "facility", "area", "zone", "subzone")


def _mem():
    return pool.STATE["mem"]["locations"]


def _row(d: dict) -> dict:
    r = {k: d.get(k) for k in _COLS}
    r["is_active"] = bool(r.get("is_active", True))
    r["sort_order"] = r.get("sort_order") or 0
    return r


# ── low-level CRUD ────────────────────────────────────────────────────────

def _fetch_rows():
    if pool.is_memory():
        return [_row(l) for l in _mem()]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM locations ORDER BY sort_order, name")
        return [_row(dict(zip(_COLS, r))) for r in cur.fetchall()]


def _all_rows():
    """The whole location table. Cached per-request: `picker()`, the admin tree
    and `resolve_for_grievance()` walk the tree recursively, and without this a
    single page load fires dozens of identical SELECTs (fine in-memory, very slow
    against a remote Postgres)."""
    try:
        from flask import g, has_request_context
        if has_request_context():
            rows = getattr(g, "_loc_rows_cache", None)
            if rows is None:
                rows = _fetch_rows()
                g._loc_rows_cache = rows
            return rows
    except Exception:  # noqa: BLE001 - no flask / no app context
        pass
    return _fetch_rows()


def _bust_cache():
    try:
        from flask import g, has_request_context
        if has_request_context() and hasattr(g, "_loc_rows_cache"):
            del g._loc_rows_cache
    except Exception:  # noqa: BLE001
        pass


def get(loc_id):
    return next((l for l in _all_rows() if l["id"] == loc_id), None)


def _by_path(full_path):
    return next((l for l in _all_rows() if l["full_path"] == full_path), None)


def list_all(active_only=True):
    rows = _all_rows()
    return [r for r in rows if r["is_active"] or not active_only]


def children(parent_id):
    kids = [l for l in _all_rows() if l["parent_id"] == parent_id and l["is_active"]]
    return sorted(kids, key=lambda l: (l["sort_order"], l["name"]))


def campus_root():
    return next((l for l in _all_rows() if l["location_type"] == "campus"), None)


def create(location_type, name, *, parent_id=None, full_path=None,
           room_type=None, bucket=None, sort_order=0):
    name = (name or "").strip()
    if not name:
        raise ValueError("location name is required")
    parent = get(parent_id) if parent_id else None
    if full_path is None:
        full_path = f"{parent['full_path']} > {name}" if parent else name
    if bucket is None and parent is not None:
        bucket = parent["bucket"]
    if _by_path(full_path):
        raise ValueError(f"location {full_path!r} already exists")

    if pool.is_memory():
        row = {"id": pool.next_seq("locations"), "parent_id": parent_id,
               "location_type": location_type, "name": name, "full_path": full_path,
               "is_active": True, "room_type": room_type, "bucket": bucket,
               "sort_order": sort_order}
        _mem().append(row)
        _bust_cache()
        return _row(row)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO locations (parent_id, location_type, name, full_path,
                                      is_active, room_type, bucket, sort_order)
               VALUES (%s,%s,%s,%s,TRUE,%s,%s,%s) RETURNING id""",
            (parent_id, location_type, name, full_path, room_type, bucket, sort_order),
        )
        cur.fetchone()
        conn.commit()
    _bust_cache()
    return _by_path(full_path)


def set_active(loc_id, active) -> None:
    """Toggle a node. Deactivating hides the whole subtree from the picker."""
    ids = {loc_id}
    if not active:
        frontier = [loc_id]
        while frontier:
            nxt = [c["id"] for c in _all_rows() if c["parent_id"] in frontier]
            ids.update(nxt)
            frontier = nxt
    if pool.is_memory():
        for l in _mem():
            if l["id"] in ids:
                l["is_active"] = active
        _bust_cache()
        return
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE locations SET is_active=%s WHERE id = ANY(%s)",
                    (active, list(ids)))
        conn.commit()
    _bust_cache()


# ── seeding: verified GL Bajaj structure only ────────────────────────────

def seed() -> None:
    root = campus_root()
    if root is None:
        root = create("campus", CAMPUS_NAME)
    rid = root["id"]

    for i, b in enumerate(CAMPUS_BUILDINGS):
        node = _by_path(f"{CAMPUS_NAME} > {b}") or create(
            "building", b, parent_id=rid, bucket="academics_block", sort_order=i)
        for j, fl in enumerate(BUILDING_FLOORS):
            if _by_path(f"{node['full_path']} > {fl}") is None:
                create("floor", fl, parent_id=node["id"], sort_order=j)

    for i, c in enumerate(CAMPUS_CANTEENS):
        if _by_path(f"{CAMPUS_NAME} > {c}") is None:
            create("facility", c, parent_id=rid, bucket="mess_canteen", sort_order=10 + i)

    for i, f in enumerate(CAMPUS_FACILITIES):
        if _by_path(f"{CAMPUS_NAME} > {f}") is None:
            create("facility", f, parent_id=rid, bucket="facility", sort_order=20 + i)

    for name, bkt, so in (("Hostels", "hostels", 30), ("Playground", "playground", 31)):
        if _by_path(f"{CAMPUS_NAME} > {name}") is None:
            create("facility", name, parent_id=rid, bucket=bkt, sort_order=so)

    outer = _by_path(f"{CAMPUS_NAME} > Outer Area") or create(
        "zone", "Outer Area", parent_id=rid, bucket="outer_area", sort_order=40)
    for i, z in enumerate(OUTER_AREA_SUBZONES):
        if _by_path(f"{outer['full_path']} > {z}") is None:
            create("subzone", z, parent_id=outer["id"], sort_order=i)


# ── picker (faculty report wizard) ───────────────────────────────────────

def _node(l: dict) -> dict:
    return {"id": l["id"], "name": l["name"], "type": l["location_type"],
            "bucket": l["bucket"], "room_type": l["room_type"],
            "children": [_node(c) for c in children(l["id"])]}


def picker() -> dict:
    root = campus_root()
    if root is None:
        return {"campus": CAMPUS_NAME, "nodes": []}
    return {"campus": root["name"],
            "nodes": [_node(c) for c in children(root["id"])]}


# ── denormalization for the grievance row ────────────────────────────────

def _chain(loc_id):
    """[campus, …, node] root-first."""
    out, cur = [], get(loc_id)
    while cur:
        out.append(cur)
        cur = get(cur["parent_id"]) if cur["parent_id"] else None
    return list(reversed(out))


def breadcrumb(loc_id) -> str:
    chain = [c for c in _chain(loc_id) if c["location_type"] != "campus"]
    return " > ".join(c["name"] for c in chain)


def resolve_for_grievance(location_id, room_free=None, area_free=None) -> dict:
    """Turn a picked node (+ optional free-text room/area) into the flat fields
    stored on the grievance row. Existing free-text-only submissions that pass
    no location_id never call this."""
    chain = _chain(location_id)
    if not chain:
        return {}
    node = chain[-1]
    by_kind = {c["location_type"]: c for c in chain}

    out = {"location_id": location_id, "location_type": node["bucket"],
           "block_no": None, "floor": None, "room": None, "sub_zone": None}

    building = by_kind.get("building")
    if building:
        out["block_no"] = building["name"]
    if "floor" in by_kind:
        out["floor"] = by_kind["floor"]["name"]
    if "room" in by_kind:
        out["room"] = by_kind["room"]["name"]
    elif room_free:
        out["room"] = room_free.strip()

    if node["location_type"] in ("facility", "zone"):
        out["block_no"] = node["name"]
    if "subzone" in by_kind:
        out["sub_zone"] = by_kind["subzone"]["name"]
    if "area" in by_kind:
        out["sub_zone"] = by_kind["area"]["name"]
    elif area_free and node["location_type"] in ("facility", "zone"):
        out["sub_zone"] = area_free.strip()

    label = breadcrumb(location_id)
    tail = out["room"] if ("room" not in by_kind and out["room"]) else \
           (out["sub_zone"] if ("area" not in by_kind and "subzone" not in by_kind
                                and out["sub_zone"]) else None)
    if tail:
        label = f"{label} > {tail}"
    out["location_label"] = label
    return out
