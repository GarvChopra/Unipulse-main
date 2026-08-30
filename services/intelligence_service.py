"""Derived campus-infrastructure analytics: KPIs, Pulse, Gap Intelligence."""
from __future__ import annotations

import time
from collections import defaultdict

from db import grievances, recurring
from domain.constants import (CATEGORIES, GAP_THRESHOLD, LOCATION_TYPES,
                              PULSE_DOMAINS, STATUSES)

_OPEN = ("reported", "verified")
_WIP = ("assigned", "in_progress")
_DONE = ("resolved", "admin_verified", "closed")
_DAY = 86400.0

_TYPE_NAMES = {t["key"]: t["name"] for t in LOCATION_TYPES}

ACTION_TEMPLATES = {
    "Electric":     "Inspect and service the electrical fittings and wiring in this area.",
    "Power":        "Check the distribution board / backup supply feeding this area.",
    "Plumbing":     "Survey the plumbing lines here for recurring leaks or blockages.",
    "Civil":        "Schedule a structural / civil inspection and planned repair for this area.",
    "Mechanical":   "Have the AC / lift / pump equipment in this area serviced by the OEM.",
    "IT / Network": "Audit the network drops and AV equipment for this area.",
}


def _all():
    return grievances.list_query(limit=100000)


def _is_breached(g, now):
    return bool(g.get("due_at") and now > g["due_at"] and g["status"] not in _DONE)


# ── KPIs ───────────────────────────────────────────────────────────────────

def kpis() -> dict:
    rows = _all()
    now = time.time()
    return {
        "total": len(rows),
        "open": sum(1 for g in rows if g["status"] in _OPEN),
        "in_progress": sum(1 for g in rows if g["status"] in _WIP),
        "resolved": sum(1 for g in rows if g["status"] in _DONE),
        "sla_breaches": sum(1 for g in rows if _is_breached(g, now)),
        "recurring": len(recurring.list_active()),
    }


def overdue(limit=20) -> list[dict]:
    now = time.time()
    breached = [g for g in _all() if _is_breached(g, now)]
    breached.sort(key=lambda g: g["due_at"])
    return breached[:limit]


# ── Infrastructure Pulse ──────────────────────────────────────────────────

def _matches(g, domain) -> bool:
    if domain["categories"] and g["category"] in domain["categories"]:
        return True
    if domain["location_type"] and g["location_type"] == domain["location_type"]:
        return True
    if domain["sub_zone"] and g["sub_zone"] == domain["sub_zone"]:
        return True
    return False


def pulse() -> list[dict]:
    rows = _all()
    now = time.time()
    active = recurring.list_active()
    out = []
    for d in PULSE_DOMAINS:
        matched = [g for g in rows if _matches(g, d)]
        open_m = [g for g in matched if g["status"] not in _DONE]
        high_open = sum(1 for g in open_m if g["severity"] == "high")
        rec = sum(1 for grp in active if grp["category"] in d["categories"])
        ages = [(now - (g["created_at"] or now)) / _DAY for g in open_m]
        avg_age = sum(ages) / len(ages) if ages else 0.0

        pen_open = min(40, 4 * len(open_m))
        pen_high = min(25, 6 * high_open)
        pen_rec = min(24, 8 * rec)
        pen_age = min(15, int(avg_age))
        score = max(0, min(100, 100 - pen_open - pen_high - pen_rec - pen_age))

        factors = []
        if pen_open:
            factors.append(f"{len(open_m)} open issues (-{pen_open})")
        if pen_high:
            factors.append(f"{high_open} high-severity (-{pen_high})")
        if pen_rec:
            factors.append(f"{rec} recurring (-{pen_rec})")
        if pen_age:
            factors.append(f"avg age {int(avg_age)}d (-{pen_age})")
        factors.sort(key=lambda s: -int(s.split("-")[-1].rstrip(")")))

        recent = sum(1 for g in open_m if (g["created_at"] or 0) >= now - 15 * _DAY)
        prior = sum(1 for g in open_m
                    if now - 30 * _DAY <= (g["created_at"] or 0) < now - 15 * _DAY)
        trend = "down" if recent > prior else ("up" if recent < prior else "flat")

        out.append({"key": d["key"], "name": d["name"], "score": score,
                    "open_count": len(open_m), "high_open": high_open,
                    "recurring_count": rec, "avg_age_days": round(avg_age, 1),
                    "factors": factors[:2], "trend": trend})
    return out


def overall_health() -> dict:
    """Overall campus-health score for the Pulse gauge (mean of domain scores)."""
    scores = [d["score"] for d in pulse()]
    val = round(sum(scores) / len(scores)) if scores else 100
    label = "Excellent" if val >= 85 else "Good" if val >= 70 else \
            "Fair" if val >= 50 else "Needs attention"
    return {"value": val, "label": label}


# ── Infrastructure Gap Intelligence ──────────────────────────────────────

def _bucket(g) -> str:
    if g["location_type"] == "academics_block" and g["block_no"]:
        return g["block_no"]
    if g["location_type"] == "outer_area" and g["sub_zone"]:
        return g["sub_zone"]
    return _TYPE_NAMES.get(g["location_type"], g["location_type"] or "Unknown")


def gaps() -> list[dict]:
    groups = defaultdict(list)
    for g in _all():
        if g["status"] == "closed" or not g["category"]:
            continue
        groups[(_bucket(g), g["category"])].append(g)

    out = []
    for (loc, cat), items in groups.items():
        if len(items) < GAP_THRESHOLD:
            continue
        rec = sum(1 for g in items if g["recurring_group_id"])
        out.append({
            "location": loc, "category": cat, "count": len(items),
            "recurring_count": rec,
            "recommended_action": ACTION_TEMPLATES.get(
                cat, "Investigate the recurring problem in this area."),
        })
    out.sort(key=lambda r: -(r["count"] + 2 * r["recurring_count"]))
    return out


# ── Analytics ──────────────────────────────────────────────────────────────

def analytics() -> dict:
    rows = _all()
    now = time.time()
    total = len(rows)

    done = [g for g in rows if g["status"] in _DONE]
    breached = sum(1 for g in rows if _is_breached(g, now))

    res_hours = [(g["resolved_at"] - g["created_at"]) / 3600
                 for g in rows
                 if g.get("resolved_at") and g.get("created_at")
                 and g["resolved_at"] >= g["created_at"]]

    by_cat = {c: 0 for c in CATEGORIES}
    for g in rows:
        if g["category"] in by_cat:
            by_cat[g["category"]] += 1

    by_status = {s: 0 for s in STATUSES}
    for g in rows:
        if g["status"] in by_status:
            by_status[g["status"]] += 1

    by_unit: dict = {}
    for g in rows:
        u = g.get("responsible_unit")
        if not u:
            continue
        slot = by_unit.setdefault(u, {"total": 0, "resolved": 0})
        slot["total"] += 1
        if g["status"] in _DONE:
            slot["resolved"] += 1

    by_loc: dict = {}
    for g in rows:
        name = _TYPE_NAMES.get(g["location_type"], g["location_type"] or "Unknown")
        by_loc[name] = by_loc.get(name, 0) + 1

    # weekly trend — grievances created per week over the last 6 weeks
    weeks = 6
    trend = []
    for w in range(weeks - 1, -1, -1):
        hi = now - w * 7 * _DAY
        lo = hi - 7 * _DAY
        n = sum(1 for g in rows if lo <= (g["created_at"] or 0) < hi)
        trend.append({"label": time.strftime("%d %b", time.localtime(hi - _DAY)), "count": n})

    cat_total = sum(by_cat.values()) or 1
    by_cat_pct = [{"name": c, "count": by_cat[c],
                   "pct": round(by_cat[c] / cat_total * 100)} for c in CATEGORIES if by_cat[c]]

    return {
        "total": total,
        "resolution_rate": round(len(done) / total * 100, 1) if total else 0.0,
        "avg_resolution_hours": round(sum(res_hours) / len(res_hours), 1) if res_hours else None,
        "sla_breach_rate": round(breached / total * 100, 1) if total else 0.0,
        "by_category": by_cat,
        "by_category_pct": by_cat_pct,
        "by_status": by_status,
        "by_unit": by_unit,
        "by_location_type": by_loc,
        "trend": trend,
    }
