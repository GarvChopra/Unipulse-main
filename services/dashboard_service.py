"""Admin dashboard composition.

One place that assembles the Super-Admin overview from the pieces that already
exist (intelligence_service, db.*). The route stays thin and the numbers stay
testable. Pure stdlib + existing modules.
"""
from __future__ import annotations

import html
import time

from db import audit, grievances, notices, recurring, users
from services import intelligence_service

_DAY = 86400.0
_OPEN = ("reported", "verified")
_WIP = ("assigned", "in_progress")
_DONE = ("resolved", "admin_verified", "closed")

# Timeframe options for the dashboard segmented control.
RANGES = [(7, "7 days"), (30, "30 days"), (90, "90 days"), (0, "All time")]
_RANGE_DAYS = {d for d, _ in RANGES}

# audit action -> (feed icon, tone)
_ACTION_ICON = {
    "user.create": ("users", ""), "admin.create": ("shield", "warn"),
    "user.activate": ("users", "ok"), "user.deactivate": ("user-x", "warn"),
    "user.deleted": ("user-x", "alert"), "user.reset_pin": ("shield", ""),
    "user.self_pin": ("shield", ""), "user.set_pin": ("shield", ""),
    "notice.create": ("notice", ""), "notice.publish": ("notice", "ok"),
    "location.create": ("location", ""), "location.toggle": ("location", "warn"),
    "recurring.resolve": ("recurring", "ok"),
    "grievance.status": ("flag", ""), "grievance.assign": ("wrench", ""),
    "grievance.category": ("layers", ""), "grievance.evidence": ("check-circle", "ok"),
    "grievance.reopen": ("recurring", "warn"), "grievance.verify": ("check", "ok"),
}

_ALERT_CACHE: dict = {"t": 0.0, "v": []}


# ── small formatters ──────────────────────────────────────────────────────

def ago(ts) -> str:
    if not ts:
        return "—"
    d = time.time() - ts
    if d < 90:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < _DAY:
        return f"{int(d // 3600)}h ago"
    if d < 7 * _DAY:
        return f"{int(d // _DAY)}d ago"
    return time.strftime("%d %b", time.localtime(ts))


def _overdue_label(due) -> str:
    d = time.time() - (due or 0)
    if d < 3600:
        return "just now"
    if d < _DAY:
        return f"{int(d // 3600)}h overdue"
    return f"{int(d // _DAY)}d overdue"


def resolve_range(raw) -> int:
    """Query-string value -> a valid range in days (0 == all time). Default 30."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 30
    return v if v in _RANGE_DAYS else 30


# ── activity feed ─────────────────────────────────────────────────────────

def _humanise(entry: dict) -> dict:
    esc = lambda v: html.escape(str(v)) if v not in (None, "") else ""
    actor = esc(entry.get("actor")) or "system"
    action = entry.get("action") or ""
    icon, tone = _ACTION_ICON.get(action, ("activity", ""))
    d = entry.get("detail") or {}
    who = esc(d.get("username") or entry.get("target_id"))
    code = esc(entry.get("target_id"))
    to = esc(d.get("to")).replace("_", " ")
    verb = {
        "user.create": f"added the account <b>{who}</b>",
        "admin.create": f"created an <b>admin</b> account ({who})",
        "user.activate": f"reactivated <b>{who}</b>",
        "user.deactivate": f"deactivated <b>{who}</b>",
        "user.deleted": f"completed deletion of <b>{who}</b>",
        "user.reset_pin": f"reset the PIN for <b>{who}</b>",
        "user.self_pin": "changed their PIN",
        "user.set_pin": "set a new PIN",
        "notice.create": "posted a campus notice",
        "notice.publish": "changed a notice's publish state",
        "location.create": f"added location <b>{esc(d.get('path'))}</b>",
        "location.toggle": "toggled a campus location",
        "recurring.resolve": "resolved a recurring issue group",
        "grievance.status": f"moved <b>{code}</b> to {to or 'a new status'}",
        "grievance.assign": f"assigned <b>{code}</b> to {esc(d.get('unit')) or 'a unit'}",
        "grievance.category": f"recategorised <b>{code}</b> as {to or 'another category'}",
        "grievance.evidence": f"added resolution evidence to <b>{code}</b>",
        "grievance.reopen": f"reopened <b>{code}</b>",
        "grievance.verify": f"verified <b>{code}</b>",
    }.get(action, "&mdash; " + esc(action.replace(".", " ")))
    return {
        "tone": tone, "icon": icon,
        "text": f"<b>{actor}</b> {verb}",
        "time": ago(entry.get("created_at")),
    }


def activity(limit: int = 8) -> list[dict]:
    out = []
    for e in audit.list_recent(limit):
        try:
            out.append(_humanise(e))
        except Exception:  # noqa: BLE001 - a bad row must not break the feed
            continue
    return out


# ── alerts (also feeds the top-bar bell on every admin page) ─────────────

def alerts(force: bool = False) -> list[dict]:
    now = time.time()
    if not force and _ALERT_CACHE["v"] is not None and now - _ALERT_CACHE["t"] < 60:
        return _ALERT_CACHE["v"]

    rows = grievances.list_query(limit=100000)
    breaches = sum(
        1 for g in rows
        if g.get("due_at") and now > g["due_at"] and g["status"] not in _DONE
    )
    high_open = sum(
        1 for g in rows if g["severity"] == "high" and g["status"] not in _DONE
    )
    rec = len(recurring.list_active())
    deletions = len(users.list_deletion_requests())
    drafts = sum(1 for n in notices.list_all() if not n["is_published"])

    items = []
    if breaches:
        items.append({"sev": "alert", "icon": "alert", "count": breaches,
                      "title": "SLA breaches",
                      "sub": "issue" + ("s" if breaches != 1 else "") + " past the response deadline",
                      "href": "/admin/grievances?sort=due"})
    if deletions:
        items.append({"sev": "alert", "icon": "user-x", "count": deletions,
                      "title": "Account deletion requests",
                      "sub": "waiting for you to complete de-identification",
                      "href": "/admin/users"})
    if high_open:
        items.append({"sev": "warn", "icon": "flag", "count": high_open,
                      "title": "High-severity issues open",
                      "sub": "unresolved, marked high severity",
                      "href": "/admin/grievances?category="})
    if rec:
        items.append({"sev": "warn", "icon": "recurring", "count": rec,
                      "title": "Active recurring issues",
                      "sub": "same place, same fault, reported repeatedly",
                      "href": "/admin/recurring"})
    if drafts:
        items.append({"sev": "info", "icon": "notice", "count": drafts,
                      "title": "Unpublished notices",
                      "sub": "draft" + ("s" if drafts != 1 else "") + " not visible to faculty yet",
                      "href": "/admin/notices"})

    _ALERT_CACHE.update(t=now, v=items)
    return items


# ── the overview payload ─────────────────────────────────────────────────

def _window_counts(rows, days: int, now: float):
    """(new, resolved) inside the window vs the window immediately before it."""
    if not days:
        new = len(rows)
        res = sum(1 for g in rows if g.get("resolved_at"))
        return new, res, None, None
    cur_lo = now - days * _DAY
    prev_lo = now - 2 * days * _DAY
    new = sum(1 for g in rows if (g.get("created_at") or 0) >= cur_lo)
    new_prev = sum(1 for g in rows
                   if prev_lo <= (g.get("created_at") or 0) < cur_lo)
    res = sum(1 for g in rows if (g.get("resolved_at") or 0) >= cur_lo)
    res_prev = sum(1 for g in rows
                   if prev_lo <= (g.get("resolved_at") or 0) < cur_lo)
    return new, res, new_prev, res_prev


def _delta(cur: int, prev, *, more_is_good: bool):
    if prev is None:
        return None
    diff = cur - prev
    if diff == 0:
        return {"dir": "flat", "text": "no change"}
    good = (diff > 0) == more_is_good
    return {"dir": "up" if good else "down",
            "text": f"{'▲' if diff > 0 else '▼'} {abs(diff)} vs prev"}


def overview(range_days: int = 30) -> dict:
    now = time.time()
    rows = grievances.list_query(limit=100000)
    k = intelligence_service.kpis()

    total = k["total"] or 1
    resolution_rate = round(k["resolved"] / total * 100, 1)
    sla_breach_rate = round(k["sla_breaches"] / total * 100, 1)

    new_n, res_n, new_prev, res_prev = _window_counts(rows, range_days, now)
    range_label = next((lbl for d, lbl in RANGES if d == range_days), "30 days")
    per = "in " + (range_label.lower() if range_days else "all time")

    kpis = [
        {"label": "Total issues", "value": k["total"], "icon": "queue",
         "href": "/admin/grievances", "sub": f"{new_n} new {per}"},
        {"label": "Open", "value": k["open"], "icon": "inbox",
         "href": "/admin/grievances?status=reported",
         "sub": "awaiting triage or assignment"},
        {"label": "In progress", "value": k["in_progress"], "icon": "wrench",
         "href": "/admin/grievances?status=in_progress",
         "sub": "assigned and being worked"},
        {"label": "Resolved", "value": k["resolved"], "tone": "ok", "icon": "check-circle",
         "href": "/admin/grievances?status=resolved",
         "sub": f"{resolution_rate}% resolution rate",
         "delta": _delta(res_n, res_prev, more_is_good=True)},
        {"label": "SLA breaches", "value": k["sla_breaches"],
         "tone": "alert" if k["sla_breaches"] else "", "icon": "alert",
         "href": "/admin/grievances?sort=due",
         "sub": f"{sla_breach_rate}% of all issues"},
        {"label": "Recurring", "value": k["recurring"],
         "tone": "warn" if k["recurring"] else "", "icon": "recurring",
         "href": "/admin/recurring", "sub": "repeat-fault groups"},
    ]

    u = users.list_all()
    employees = {
        "total": sum(1 for x in u if x["role"] == "reporter"),
        "active": sum(1 for x in u if x["role"] == "reporter" and x["is_active"]),
        "admins": sum(1 for x in u if x["role"] == "admin" and x["is_active"]),
        "pending_deletion": sum(1 for x in u if x.get("deletion_requested")),
    }

    overdue_rows = [{
        "code": g["code"],
        "category": g["category"] or "Unclassified",
        "location": g["location_label"],
        "unit": g["responsible_unit"] or "—",
        "due": _overdue_label(g["due_at"]),
        "status": g["status"],
        "_href": f"/admin/grievances/{g['code']}",
        "_overdue": True,
    } for g in intelligence_service.overdue(6)]

    recurring_rows = [{
        "title": grp["title"],
        "category": grp["category"],
        "location": grp["location_label"],
        "reports": grp["report_count"],
        "people": f"{grp['reporter_count']} staff",
        "_href": "/admin/recurring",
    } for grp in recurring.list_active()[:5]]

    quick_actions = [
        {"label": "Review queue", "href": "/admin/grievances", "icon": "queue"},
        {"label": "Post a notice", "href": "/admin/notices", "icon": "notice"},
        {"label": "Add employee", "href": "/admin/users", "icon": "users"},
        {"label": "Export report", "href": "/admin/reports", "icon": "download"},
        {"label": "Manage locations", "href": "/admin/locations", "icon": "location"},
        {"label": "Infrastructure gaps", "href": "/admin/gaps", "icon": "gaps"},
    ]

    return {
        "range_days": range_days,
        "range_label": range_label,
        "ranges": RANGES,
        "kpis": kpis,
        "employees": employees,
        "overdue_rows": overdue_rows,
        "recurring_rows": recurring_rows,
        "quick_actions": quick_actions,
        "generated_at": now,
    }
