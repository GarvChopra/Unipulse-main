# UniPulse — Phase C + D (Super Admin Portal + Intelligence) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The Super Admin ("Sir") logs in and, from one responsive web portal, sees a
KPI dashboard + Infrastructure Pulse, works a priority-ranked grievance queue
(recurring issues collapsed to one row), and drives every grievance through
`verify → correct category → assign to a Responsible Unit (+SLA due date) →
in progress → resolved (evidence required) → admin verified → closed`, with a full
audit trail. Plus Recurring, Gap Intelligence, and CRUD for notices / faculty
accounts / campus locations.

**Architecture:** New `admin` Flask blueprint (`/admin/*`) on the Phase-0/A app
factory, gated by role + `@require_permission`. Workflow logic lives in
`services/grievance_service` (transitions validated against
`STATUS_TRANSITIONS`, resolved-gate enforced, every change writes a
`timeline_event` + `audit_log` and recomputes `priority_score`). Derived analytics
live in a new `services/intelligence_service`. Server-rendered Jinja + vanilla JS.

**Tech Stack:** Python 3.12, Flask 3, pytest 9. No new pip deps.

**Spec:** `docs/superpowers/specs/2026-08-30-unipulse-campus-design.md` (§5 units,
§6 RBAC, §9 priority, §10 Pulse/Gap, §12 phases C+D). Builds on Phase 0/A and
Phase B (both done, 87 tests passing).

## Global Constraints

- Product **UniPulse** / **GL Bajaj**. Roles `reporter`/`admin` only.
- Categories: `Electric, Plumbing, Civil, Mechanical, Power, IT / Network`.
- Statuses forward-only + logged reopen: `STATUS_TRANSITIONS` in `domain/constants.py` is the single source of truth. `resolved` requires an `evidence(kind='resolution_after')` row **with a non-empty note**.
- Responsible Units: `RESPONSIBLE_UNITS_FLAT` (Infrastructure, Sanitation, Housekeeping, Landscaping, Mess, Parking, Class, Lab).
- `SLA_HOURS[category]` drives `due_at = assigned_at + hours*3600`. Overdue = `now > due_at and status not in (resolved, admin_verified, closed)`.
- `GAP_THRESHOLD = 4`. Priority queue default sort = `priority`.
- Every mutating admin action: `timeline.add(...)` (grievance-scoped) and/or `audit.add(...)` (portal-scoped), then `grievance_service.recompute_priority(gid)` where the change affects the score.
- Timestamps epoch floats. No `session`. Tests in-memory; Groq unavailable.
- No commits.

---

## File Structure

**Created:**
- `services/intelligence_service.py` — `kpis()`, `pulse()`, `gaps()`, `overdue()`
- `blueprints/admin/__init__.py` — the whole admin portal
- `templates/admin/dashboard.html`, `queue.html`, `detail.html`, `recurring.html`, `pulse.html`, `gaps.html`, `notices.html`, `users.html`, `locations.html`, `audit.html`
- `static/js/admin_queue.js`
- `tests/test_workflow.py`, `tests/test_resolution_gate.py`, `tests/test_intelligence.py`, `tests/test_admin_rbac.py`, `tests/test_admin_routes.py`

**Modified:**
- `services/grievance_service.py` — add `transition`, `assign`, `correct_category`, `reopen`, `add_note`, `add_resolution_evidence`, `recompute_priority`, `recompute_open`
- `db/schema.py` + `db/grievances.py` — add `spam_flag BOOLEAN` column
- `db/recurring.py` — add `members(group_id)` helper
- `app.py` — register `admin` blueprint
- `templates/base_admin.html` — real responsive shell + nav
- `static/css/app.css` — admin table/card styles

---

## Phase C — Super Admin Portal

### Task 1: `spam_flag` column + persist it

**Files:** Modify `db/schema.py`, `db/grievances.py`, `services/grievance_service.py`
**Test:** `tests/test_grievance_pipeline.py` (extend)

**Interfaces:**
- `grievances` row gains `spam_flag: bool` (default False). `grievances.insert(**)` accepts `spam_flag`.

- [ ] **Step 1:** In `db/schema.py` `DDL`, add to the `grievances` table (after `ai_confidence INTEGER,`):

```sql
    spam_flag          BOOLEAN DEFAULT FALSE,
```

- [ ] **Step 2:** In `db/grievances.py`:
  - add `"spam_flag"` to `_COLS` (right after `"ai_confidence"`)
  - add `"spam_flag": False` to `_DEFAULTS`

- [ ] **Step 3:** In `services/grievance_service.py` `submit()`, pass it to `grievances.insert(...)`:

```python
        ai_summary=cls["ai_summary"], ai_confidence=cls["confidence"],
        spam_flag=cls["spam_flag"],
```

- [ ] **Step 4:** Add to `tests/test_grievance_pipeline.py`:

```python
def test_spam_flag_persisted(memstore):
    from db import users
    u = users.create("sp", "SP", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"], description="asdf asdf test test 12345"))
    assert grievances.get_by_code(out["code"])["spam_flag"] is True
```

- [ ] **Step 5:** `pytest tests/test_grievance_pipeline.py -q` → PASS (6).

---

### Task 2: `grievance_service` workflow functions

**Files:** Modify `services/grievance_service.py`, `db/recurring.py`
**Test:** `tests/test_workflow.py`

**Interfaces:**
- `db.recurring.members(group_id) -> list[dict]` — grievances with that `recurring_group_id`.
- `grievance_service`:
  - `WorkflowError(Exception)` with `.message: str`
  - `recompute_priority(gid: int) -> int` — reload grievance + its active recurring group, `priority_score`, persist, return it.
  - `recompute_open() -> None` — `recompute_priority` for every grievance whose status is not in `("closed",)`.
  - `transition(gid, to_status, *, actor, actor_role, note=None) -> dict` — validates against `STATUS_TRANSITIONS[current]`; raises `WorkflowError` otherwise. On `to_status == "resolved"` requires a `resolution_after` evidence row **with a note** (else `WorkflowError`). Sets `resolved_at`/`closed_at`; a `resolved|admin_verified → in_progress` move clears `resolved_at` and logs event_type `reopened`. Writes `timeline_events` (`status_change`, from/to) + `audit_log`, recomputes priority. Returns the updated grievance.
  - `assign(gid, *, unit, assignee, actor, due_at=None) -> dict` — current status must be `verified`; `unit` in `RESPONSIBLE_UNITS_FLAT`. `due_at` defaults to `now + SLA_HOURS.get(category, 72)*3600`. Sets `responsible_unit, assignee, assigned_at, due_at, status='assigned'`; timeline `assigned` (to_value=unit) + audit + recompute.
  - `correct_category(gid, *, category, actor) -> dict` — `category` in `CATEGORIES`; sets `category, category_confirmed=True`; timeline `category_corrected` (from/to) + audit + recompute.
  - `add_note(gid, *, actor, actor_role, text) -> dict` — timeline `note`.
  - `reopen(gid, *, actor, note=None) -> dict` — thin wrapper: `transition(gid, "in_progress", ...)` when current is `resolved`/`admin_verified`.

- [ ] **Step 1:** Add `members` to `db/recurring.py`:

```python
def members(group_id):
    from db import grievances
    return [g for g in grievances.list_query(limit=100000)
            if g.get("recurring_group_id") == group_id]
```

- [ ] **Step 2:** Write `tests/test_workflow.py`

```python
import time

import pytest

from db import evidence, grievances, timeline, users
from services import grievance_service as gs
from services.auth_service import hash_pin


def _grievance(memstore, category="Electric", status="reported"):
    u = users.create("f", "Faculty", "reporter", hash_pin("1"))
    g = grievances.insert(reporter_id=u["id"], reporter_name="Faculty", title="t",
                          description="the ceiling fan is not working in this room",
                          location_type="academics_block", block_no="Block B",
                          location_label="Academics Block > Block B > 2nd Floor > Room 204",
                          category=category, severity="medium", status=status,
                          priority_score=10)
    return g


def test_verify_then_assign_sets_sla_due(memstore):
    g = _grievance(memstore, category="Electric")
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    out = gs.assign(g["id"], unit="Infrastructure", assignee="Ravi (electrician)", actor="admin")
    assert out["status"] == "assigned"
    assert out["responsible_unit"] == "Infrastructure"
    # Electric SLA = 24h
    assert abs(out["due_at"] - (out["assigned_at"] + 24 * 3600)) < 5
    events = [e["event_type"] for e in timeline.list_for(g["id"])]
    assert "status_change" in events and "assigned" in events


def test_illegal_transition_rejected(memstore):
    g = _grievance(memstore)
    with pytest.raises(gs.WorkflowError):
        gs.transition(g["id"], "closed", actor="admin", actor_role="admin")


def test_assign_requires_verified(memstore):
    g = _grievance(memstore, status="reported")
    with pytest.raises(gs.WorkflowError):
        gs.assign(g["id"], unit="Infrastructure", assignee="x", actor="admin")


def test_correct_category_recomputes_priority(memstore):
    g = _grievance(memstore, category="IT / Network")   # low risk (+3)
    before = grievances.get_by_id(g["id"])["priority_score"]
    gs.correct_category(g["id"], category="Electric", actor="admin")  # +15
    after = grievances.get_by_id(g["id"])["priority_score"]
    assert after > before
    assert grievances.get_by_id(g["id"])["category_confirmed"] is True


def test_full_lifecycle_to_closed(memstore):
    g = _grievance(memstore)
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(g["id"], unit="Infrastructure", assignee="team", actor="admin")
    gs.transition(g["id"], "in_progress", actor="admin", actor_role="admin")
    evidence.add(g["id"], "resolution_after", image_url="data:image/png;base64,aGk=",
                 note="Replaced the fan capacitor", uploaded_by="admin")
    gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    assert grievances.get_by_id(g["id"])["resolved_at"] is not None
    gs.transition(g["id"], "admin_verified", actor="admin", actor_role="admin")
    gs.transition(g["id"], "closed", actor="admin", actor_role="admin")
    assert grievances.get_by_id(g["id"])["closed_at"] is not None


def test_reopen_clears_resolved_at(memstore):
    g = _grievance(memstore)
    for s in ("verified", "assigned"):
        pass
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(g["id"], unit="Infrastructure", assignee="t", actor="admin")
    gs.transition(g["id"], "in_progress", actor="admin", actor_role="admin")
    evidence.add(g["id"], "resolution_after", image_url="data:image/png;base64,aGk=",
                 note="fixed", uploaded_by="admin")
    gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    gs.reopen(g["id"], actor="admin", note="Problem came back")
    row = grievances.get_by_id(g["id"])
    assert row["status"] == "in_progress"
    assert row["resolved_at"] is None
    assert "reopened" in [e["event_type"] for e in timeline.list_for(g["id"])]
```

- [ ] **Step 3:** Run — fails.

- [ ] **Step 4:** Add to `services/grievance_service.py` (append after `submit`):

```python
from db import audit, recurring
from domain.constants import CATEGORIES, RESPONSIBLE_UNITS_FLAT, SLA_HOURS, STATUS_TRANSITIONS


class WorkflowError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _load(gid: int) -> dict:
    g = grievances.get_by_id(gid)
    if not g:
        raise WorkflowError(f"Grievance {gid} not found")
    return g


def recompute_priority(gid: int) -> int:
    g = _load(gid)
    grp = recurring.get(g["recurring_group_id"]) if g.get("recurring_group_id") else None
    score = classification_service.priority_score(g, recurring_group=grp)
    grievances.update(gid, priority_score=score)
    return score


def recompute_open() -> None:
    for g in grievances.list_query(limit=100000):
        if g["status"] != "closed":
            recompute_priority(g["id"])


def transition(gid, to_status, *, actor, actor_role, note=None) -> dict:
    g = _load(gid)
    cur = g["status"]
    if to_status not in STATUS_TRANSITIONS.get(cur, []):
        raise WorkflowError(f"Cannot move a {cur} grievance to {to_status}.")

    is_reopen = to_status == "in_progress" and cur in ("resolved", "admin_verified")

    if to_status == "resolved":
        after = [e for e in evidence.list_for(gid) if e["kind"] == "resolution_after"]
        if not after or not any((e.get("note") or "").strip() for e in after):
            raise WorkflowError(
                "Upload an 'after' photo and a resolution note before marking this resolved.")

    patch = {"status": to_status}
    now = time.time()
    if to_status == "resolved":
        patch["resolved_at"] = now
    if to_status == "closed":
        patch["closed_at"] = now
    if is_reopen:
        patch["resolved_at"] = None
        patch["closed_at"] = None
    grievances.update(gid, **patch)

    timeline.add(gid, "reopened" if is_reopen else "status_change",
                 from_value=cur, to_value=to_status, actor=actor, actor_role=actor_role,
                 note=note)
    audit.add(actor, "grievance.reopen" if is_reopen else "grievance.status",
              target_type="grievance", target_id=g["code"],
              detail={"from": cur, "to": to_status})
    recompute_priority(gid)
    return grievances.get_by_id(gid)


def assign(gid, *, unit, assignee, actor, due_at=None) -> dict:
    g = _load(gid)
    if g["status"] != "verified":
        raise WorkflowError("Verify the grievance before assigning it.")
    if unit not in RESPONSIBLE_UNITS_FLAT:
        raise WorkflowError(f"Unknown responsible unit {unit!r}.")
    now = time.time()
    if due_at is None:
        hours = SLA_HOURS.get(g["category"], 72)
        due_at = now + hours * 3600
    grievances.update(gid, responsible_unit=unit, assignee=assignee, assigned_at=now,
                      due_at=due_at, status="assigned")
    timeline.add(gid, "assigned", to_value=unit, actor=actor, actor_role="admin",
                 note=f"{assignee}" if assignee else None)
    audit.add(actor, "grievance.assign", target_type="grievance", target_id=g["code"],
              detail={"unit": unit, "assignee": assignee})
    recompute_priority(gid)
    return grievances.get_by_id(gid)


def correct_category(gid, *, category, actor) -> dict:
    g = _load(gid)
    if category not in CATEGORIES:
        raise WorkflowError(f"Unknown category {category!r}.")
    old = g["category"]
    grievances.update(gid, category=category, category_confirmed=True)
    timeline.add(gid, "category_corrected", from_value=old, to_value=category,
                 actor=actor, actor_role="admin")
    audit.add(actor, "grievance.category", target_type="grievance", target_id=g["code"],
              detail={"from": old, "to": category})
    recompute_priority(gid)
    return grievances.get_by_id(gid)


def add_note(gid, *, actor, actor_role, text) -> dict:
    g = _load(gid)
    timeline.add(gid, "note", actor=actor, actor_role=actor_role, note=text)
    return g


def add_resolution_evidence(gid, *, kind, image_b64, mime, note, actor) -> dict:
    g = _load(gid)
    if kind not in ("resolution_before", "resolution_after"):
        raise WorkflowError("Evidence kind must be resolution_before or resolution_after.")
    url = storage_service.upload_image(image_b64 or "", mime or "image/jpeg")
    evidence.add(gid, kind, image_url=url, thumbnail_url=url, note=note, uploaded_by=actor)
    timeline.add(gid, "evidence_added", to_value=kind, actor=actor, actor_role="admin",
                 note=note)
    audit.add(actor, "grievance.evidence", target_type="grievance", target_id=g["code"],
              detail={"kind": kind})
    return grievances.get_by_id(gid)


def reopen(gid, *, actor, note=None) -> dict:
    return transition(gid, "in_progress", actor=actor, actor_role="admin",
                      note=note or "Reopened by admin")
```

- [ ] **Step 5:** Run `pytest tests/test_workflow.py -q` → PASS (6).

---

### Task 3: resolution-gate dedicated tests

**Files:** Test only — `tests/test_resolution_gate.py`

- [ ] **Step 1:** Write `tests/test_resolution_gate.py`

```python
import pytest

from db import evidence, grievances, users
from services import grievance_service as gs
from services.auth_service import hash_pin


def _in_progress(memstore):
    u = users.create("f", "F", "reporter", hash_pin("1"))
    g = grievances.insert(reporter_id=u["id"], reporter_name="F", title="t",
                          description="the tubelight is not working here",
                          location_type="hostels", location_label="Hostels",
                          category="Electric", severity="medium", status="reported",
                          priority_score=10)
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(g["id"], unit="Infrastructure", assignee="t", actor="admin")
    gs.transition(g["id"], "in_progress", actor="admin", actor_role="admin")
    return g


def test_resolve_blocked_without_evidence(memstore):
    g = _in_progress(memstore)
    with pytest.raises(gs.WorkflowError) as ei:
        gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    assert "after" in ei.value.message.lower()


def test_resolve_blocked_with_evidence_but_no_note(memstore):
    g = _in_progress(memstore)
    evidence.add(g["id"], "resolution_after", image_url="data:image/png;base64,aGk=",
                 note="", uploaded_by="admin")
    with pytest.raises(gs.WorkflowError):
        gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")


def test_resolve_allowed_with_evidence_and_note(memstore):
    g = _in_progress(memstore)
    gs.add_resolution_evidence(g["id"], kind="resolution_after",
                               image_b64="aGk=", mime="image/png",
                               note="Replaced the tubelight and the choke", actor="admin")
    out = gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    assert out["status"] == "resolved"
```

- [ ] **Step 2:** Run — PASS (3).

---

### Task 4: `intelligence_service` — KPIs + overdue

**Files:** Create `services/intelligence_service.py`
**Test:** `tests/test_intelligence.py` (KPI portion)

**Interfaces:**
- `intelligence_service`:
  - `kpis() -> dict` → `{total, open, in_progress, resolved, sla_breaches, recurring}`
    - open = status in (`reported`,`verified`); in_progress = (`assigned`,`in_progress`); resolved = (`resolved`,`admin_verified`,`closed`)
    - sla_breaches = `due_at` set, `now > due_at`, status not in (`resolved`,`admin_verified`,`closed`)
    - recurring = `len(recurring.list_active())`
  - `overdue(limit=20) -> list[dict]` — breached grievances, worst (most overdue) first.

- [ ] **Step 1:** Write `tests/test_intelligence.py` (KPI part)

```python
import time

from db import grievances, recurring, users
from services import intelligence_service as si
from services.auth_service import hash_pin


def _g(memstore, **kw):
    u = kw.pop("_u", None) or users.create(f"u{time.time_ns()}", "U", "reporter", hash_pin("1"))
    base = dict(reporter_id=u["id"], reporter_name="U", title="t",
                description="a broken item is here now", location_type="hostels",
                location_label="Hostels", category="Electric", severity="medium",
                status="reported", priority_score=10)
    base.update(kw)
    return grievances.insert(**base)


def test_kpis_counts(memstore):
    _g(memstore, status="reported")
    _g(memstore, status="assigned")
    _g(memstore, status="resolved")
    g = _g(memstore, status="in_progress")
    grievances.update(g["id"], due_at=time.time() - 3600)   # overdue
    k = si.kpis()
    assert k["total"] == 4
    assert k["open"] == 1
    assert k["in_progress"] == 2
    assert k["resolved"] == 1
    assert k["sla_breaches"] == 1


def test_recurring_kpi(memstore):
    recurring.create("Hostels", "Electric", "t", 1, time.time())
    assert si.kpis()["recurring"] == 1


def test_overdue_sorted_worst_first(memstore):
    a = _g(memstore, status="assigned"); grievances.update(a["id"], due_at=time.time() - 100)
    b = _g(memstore, status="assigned"); grievances.update(b["id"], due_at=time.time() - 9999)
    ov = si.overdue()
    assert [x["id"] for x in ov] == [b["id"], a["id"]]
```

- [ ] **Step 2:** Write `services/intelligence_service.py` (KPI + overdue only for now; pulse/gaps added in Tasks 12-13)

```python
"""Derived campus-infrastructure analytics: KPIs, Pulse, Gap Intelligence."""
from __future__ import annotations

import time

from db import grievances, recurring

_OPEN = ("reported", "verified")
_WIP = ("assigned", "in_progress")
_DONE = ("resolved", "admin_verified", "closed")


def _all():
    return grievances.list_query(limit=100000)


def _is_breached(g, now):
    return (g.get("due_at") and now > g["due_at"]
            and g["status"] not in _DONE)


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
    breached.sort(key=lambda g: g["due_at"])   # most overdue (smallest due_at) first
    return breached[:limit]
```

- [ ] **Step 3:** Run `pytest tests/test_intelligence.py -q` → PASS (3).

---

### Task 5: `admin` blueprint skeleton + dashboard + base template + register

**Files:** Create `blueprints/admin/__init__.py`, `templates/admin/dashboard.html`; modify `app.py`, `templates/base_admin.html`, `static/css/app.css`
**Test:** `tests/test_admin_rbac.py`

**Interfaces:**
- Blueprint `admin`, url_prefix `/admin`. `before_request`: not logged in → `/login`; role != admin → 403.
- `GET /admin` → dashboard: `kpis`, `overdue`, `recurring.list_active()[:5]`, recent `audit.list_recent(10)`.
- Jinja: uses `can()` from the app context processor.

- [ ] **Step 1:** Write `blueprints/admin/__init__.py` (dashboard only for now — queue/detail/CRUD appended in later tasks)

```python
"""Super Admin portal: dashboard, queue, workflow, recurring, pulse, gaps, CRUD, audit."""
from flask import Blueprint, abort, g, redirect, render_template

from db import audit, recurring
from services import intelligence_service

bp = Blueprint("admin", __name__, url_prefix="/admin",
               template_folder="../../templates")


@bp.before_request
def _guard():
    if not g.get("current_user"):
        return redirect("/login")
    if g.current_user["role"] != "admin":
        abort(403)


@bp.get("/")
def dashboard():
    return render_template(
        "admin/dashboard.html",
        kpis=intelligence_service.kpis(),
        overdue=intelligence_service.overdue(8),
        recurring=recurring.list_active()[:5],
        activity=audit.list_recent(10),
    )
```

- [ ] **Step 2:** Register in `app.py` after the faculty blueprint:

```python
    from blueprints.admin import bp as admin_bp
    app.register_blueprint(admin_bp)
```

- [ ] **Step 3:** Rewrite `templates/base_admin.html`

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="{{ GLB.theme_navy }}">
  <title>{% block title %}Admin{% endblock %} &middot; UniPulse</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
</head>
<body class="admin">
  <header class="topbar">
    <strong>UniPulse Admin</strong> &middot; {{ GLB.short }}
    {% if current_user %}<a href="/logout" class="right">Log out</a>{% endif %}
  </header>
  <nav class="adminnav">
    {% set p = request.path %}
    <a href="/admin" class="{{ 'on' if p == '/admin' }}">Dashboard</a>
    <a href="/admin/grievances" class="{{ 'on' if p.startswith('/admin/grievances') }}">Queue</a>
    <a href="/admin/recurring" class="{{ 'on' if p == '/admin/recurring' }}">Recurring</a>
    <a href="/admin/pulse" class="{{ 'on' if p == '/admin/pulse' }}">Pulse</a>
    <a href="/admin/gaps" class="{{ 'on' if p == '/admin/gaps' }}">Gaps</a>
    <a href="/admin/notices" class="{{ 'on' if p == '/admin/notices' }}">Notices</a>
    <a href="/admin/users" class="{{ 'on' if p == '/admin/users' }}">Faculty</a>
    <a href="/admin/locations" class="{{ 'on' if p == '/admin/locations' }}">Locations</a>
    <a href="/admin/audit" class="{{ 'on' if p == '/admin/audit' }}">Audit</a>
  </nav>
  <main>{% block content %}{% endblock %}</main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4:** Append to `static/css/app.css`

```css
.adminnav { background:#0e356e; display:flex; flex-wrap:wrap; padding:0 8px; }
.adminnav a { color:#cfe0ff; text-decoration:none; padding:10px 12px; font-size:13.5px; }
.adminnav a.on { color:#fff; border-bottom:2px solid #fff; font-weight:700; }
.kpi-row { display:flex; flex-wrap:wrap; gap:12px; }
.kpi { flex:1 1 130px; background:#fff; border:1px solid var(--line); border-radius:10px; padding:14px; }
.kpi b { font-size:26px; display:block; }
table.grid { width:100%; border-collapse:collapse; background:#fff; }
table.grid th, table.grid td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); font-size:13.5px; }
table.grid tr:hover td { background:#f4f7ff; }
.filters { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
.filters select, .filters input { width:auto; }
.bar { height:10px; background:#e7ecf5; border-radius:6px; overflow:hidden; }
.bar > span { display:block; height:100%; background:var(--glb-blue); }
form.inline { display:inline; }
@media (max-width:640px){
  table.grid, table.grid tbody, table.grid tr, table.grid td { display:block; }
  table.grid thead { display:none; }
  table.grid tr { border:1px solid var(--line); border-radius:8px; margin-bottom:10px; padding:6px; }
  table.grid td { border:0; padding:4px 6px; }
}
```

- [ ] **Step 5:** Write `templates/admin/dashboard.html`

```html
{% extends "base_admin.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<h2>Campus overview</h2>
<div class="kpi-row">
  <div class="kpi"><b>{{ kpis.total }}</b>Total</div>
  <div class="kpi"><b>{{ kpis.open }}</b>Open</div>
  <div class="kpi"><b>{{ kpis.in_progress }}</b>In progress</div>
  <div class="kpi"><b>{{ kpis.resolved }}</b>Resolved</div>
  <div class="kpi"><b>{{ kpis.sla_breaches }}</b>SLA breaches</div>
  <div class="kpi"><b>{{ kpis.recurring }}</b>Recurring</div>
</div>

<h3>Overdue</h3>
{% if overdue %}
<table class="grid">
  <thead><tr><th>Code</th><th>Category</th><th>Location</th><th>Unit</th></tr></thead>
  <tbody>{% for g in overdue %}
    <tr onclick="location='/admin/grievances/{{ g.code }}'">
      <td>{{ g.code }}</td><td>{{ g.category or '-' }}</td>
      <td>{{ g.location_label }}</td><td>{{ g.responsible_unit or '-' }}</td>
    </tr>{% endfor %}</tbody>
</table>
{% else %}<p class="muted">Nothing overdue.</p>{% endif %}

<h3>Active recurring issues</h3>
{% for r in recurring %}
<div class="card"><strong>{{ r.title }}</strong> &middot; {{ r.report_count }} reports
  from {{ r.reporter_count }} faculty <a href="/admin/recurring">manage &rsaquo;</a></div>
{% else %}<p class="muted">None.</p>{% endfor %}

<h3>Recent activity</h3>
<table class="grid"><tbody>
{% for a in activity %}<tr><td>{{ a.action }}</td><td>{{ a.target_id or '' }}</td>
  <td class="muted">{{ a.actor }}</td></tr>{% endfor %}
</tbody></table>
{% endblock %}
```

- [ ] **Step 6:** Write `tests/test_admin_rbac.py`

```python
def test_admin_dashboard_requires_admin(client):
    # anonymous
    r = client.get("/admin")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    # faculty
    client.post("/login", data={"username": "prof.rao", "pin": "1234"})
    assert client.get("/admin").status_code == 403


def test_admin_can_see_dashboard(client):
    client.post("/login", data={"username": "admin", "pin": "0000"})
    r = client.get("/admin")
    assert r.status_code == 200
    assert b"Campus overview" in r.data
```

- [ ] **Step 7:** Run `pytest tests/test_admin_rbac.py -q` → PASS (2).

---

### Task 6: Grievance queue + `/data` (filters, sort, search, recurring collapse)

**Files:** Modify `blueprints/admin/__init__.py`; create `templates/admin/queue.html`, `static/js/admin_queue.js`
**Test:** `tests/test_admin_routes.py` (queue portion)

**Interfaces:**
- `GET /admin/grievances` → `queue.html` with filter option lists (`CATEGORIES`, `STATUSES`, `RESPONSIBLE_UNITS_FLAT`, `LOCATION_TYPES`).
- `GET /admin/grievances/data?category=&status=&unit=&location_type=&search=&sort=` → JSON:
  `{rows: [ {code|null, group_id|null, title, category, status, location_label, priority_score, report_count, reporter_name, due_at, overdue: bool, is_group: bool} ]}`.
  **Recurring collapse:** grievances sharing an active `recurring_group_id` are represented by ONE row (`is_group=true`, `group_id` set, `code=null`, `report_count`=group count, `status`= the "least done" member status, `priority_score`= max member score). Ungrouped grievances are normal rows. Calls `grievance_service.recompute_open()` first.

- [ ] **Step 1:** Add to `blueprints/admin/__init__.py`

```python
import time as _time

from flask import request

from db import grievances, recurring
from domain.constants import (CATEGORIES, LOCATION_TYPES, RESPONSIBLE_UNITS_FLAT,
                              STATUSES)
from services import grievance_service

_STATUS_RANK = {s: i for i, s in enumerate(STATUSES)}


@bp.get("/grievances")
def queue_page():
    return render_template("admin/queue.html", categories=CATEGORIES, statuses=STATUSES,
                           units=RESPONSIBLE_UNITS_FLAT, location_types=LOCATION_TYPES)


@bp.get("/grievances/data")
def queue_data():
    grievance_service.recompute_open()
    rows = grievances.list_query(
        status=request.args.get("status") or None,
        category=request.args.get("category") or None,
        responsible_unit=request.args.get("unit") or None,
        location_type=request.args.get("location_type") or None,
        search=request.args.get("search") or None,
        sort=request.args.get("sort") or "priority",
        limit=500,
    )
    now = _time.time()
    active_groups = {gr["id"]: gr for gr in recurring.list_active()}

    grouped: dict[int, list] = {}
    singles = []
    for g in rows:
        gid = g.get("recurring_group_id")
        if gid in active_groups:
            grouped.setdefault(gid, []).append(g)
        else:
            singles.append(g)

    def _row(g, overdue):
        return {
            "code": g["code"], "group_id": None, "title": g["title"],
            "category": g["category"], "status": g["status"],
            "location_label": g["location_label"], "priority_score": g["priority_score"],
            "report_count": 1, "reporter_name": g["reporter_name"],
            "due_at": g["due_at"], "overdue": overdue, "is_group": False,
        }

    out = []
    for g in singles:
        overdue = bool(g["due_at"] and now > g["due_at"]
                       and g["status"] not in ("resolved", "admin_verified", "closed"))
        out.append(_row(g, overdue))
    for gid, members in grouped.items():
        grp = active_groups[gid]
        lead = min(members, key=lambda m: _STATUS_RANK.get(m["status"], 0))
        overdue = any(m["due_at"] and now > m["due_at"]
                      and m["status"] not in ("resolved", "admin_verified", "closed")
                      for m in members)
        out.append({
            "code": None, "group_id": gid, "title": grp["title"],
            "category": grp["category"], "status": lead["status"],
            "location_label": grp["location_label"],
            "priority_score": max(m["priority_score"] for m in members),
            "report_count": grp["report_count"], "reporter_name": f"{grp['reporter_count']} faculty",
            "due_at": lead["due_at"], "overdue": overdue, "is_group": True,
        })
    out.sort(key=lambda r: (-r["priority_score"],))
    return {"rows": out}
```

- [ ] **Step 2:** Write `templates/admin/queue.html`

```html
{% extends "base_admin.html" %}
{% block title %}Queue{% endblock %}
{% block content %}
<h2>Grievance queue</h2>
<div class="filters">
  <select id="f-status"><option value="">Any status</option>
    {% for s in statuses %}<option>{{ s }}</option>{% endfor %}</select>
  <select id="f-category"><option value="">Any category</option>
    {% for c in categories %}<option>{{ c }}</option>{% endfor %}</select>
  <select id="f-unit"><option value="">Any unit</option>
    {% for u in units %}<option>{{ u }}</option>{% endfor %}</select>
  <select id="f-loc"><option value="">Any location type</option>
    {% for t in location_types %}<option value="{{ t.key }}">{{ t.name }}</option>{% endfor %}</select>
  <input id="f-search" placeholder="Search code / text / reporter">
  <select id="f-sort"><option value="priority">Priority</option>
    <option value="created">Newest</option><option value="due">Due date</option></select>
</div>
<table class="grid">
  <thead><tr><th>Priority</th><th>Ref</th><th>Category</th><th>Status</th>
    <th>Location</th><th>Reports</th><th>Due</th></tr></thead>
  <tbody id="rows"><tr><td colspan="7" class="muted">Loading&hellip;</td></tr></tbody>
</table>
{% endblock %}
{% block scripts %}<script src="{{ url_for('static', filename='js/admin_queue.js') }}"></script>{% endblock %}
```

- [ ] **Step 3:** Write `static/js/admin_queue.js`

```javascript
(() => {
  const ids = ["f-status", "f-category", "f-unit", "f-loc", "f-search", "f-sort"];
  const q = () => {
    const p = new URLSearchParams();
    const v = (id) => document.getElementById(id).value;
    if (v("f-status")) p.set("status", v("f-status"));
    if (v("f-category")) p.set("category", v("f-category"));
    if (v("f-unit")) p.set("unit", v("f-unit"));
    if (v("f-loc")) p.set("location_type", v("f-loc"));
    if (v("f-search")) p.set("search", v("f-search"));
    p.set("sort", v("f-sort"));
    return p.toString();
  };
  const load = async () => {
    const tb = document.getElementById("rows");
    tb.innerHTML = `<tr><td colspan="7" class="muted">Loading…</td></tr>`;
    const { rows } = await (await fetch("/admin/grievances/data?" + q())).json();
    if (!rows.length) { tb.innerHTML = `<tr><td colspan="7" class="muted">No grievances.</td></tr>`; return; }
    tb.innerHTML = rows.map((r) => {
      const href = r.is_group ? `/admin/recurring#g${r.group_id}` : `/admin/grievances/${r.code}`;
      return `<tr onclick="location='${href}'" style="cursor:pointer">
        <td><strong>${r.priority_score}</strong></td>
        <td>${r.is_group ? "RECURRING" : r.code}</td>
        <td>${r.category || "-"}</td>
        <td><span class="chip ${r.status}">${r.status.replace("_", " ")}</span></td>
        <td>${r.location_label}</td>
        <td>${r.report_count}${r.is_group ? " ⟳" : ""}</td>
        <td>${r.overdue ? "<strong style='color:#b91c1c'>overdue</strong>" : (r.due_at ? "set" : "-")}</td>
      </tr>`;
    }).join("");
  };
  ids.forEach((id) => document.getElementById(id).addEventListener("input", load));
  load();
})();
```

- [ ] **Step 4:** Write `tests/test_admin_routes.py` (queue portion)

```python
from db import grievances, users
from services import grievance_service as gs
from services.auth_service import hash_pin


def _admin(client):
    client.post("/login", data={"username": "admin", "pin": "0000"})


def _report(client, user="prof.rao", desc="the ceiling fan is not working in this room",
            label="Academics Block > Block B > 2nd Floor > Room 204"):
    c = client.application.test_client()
    c.post("/login", data={"username": user, "pin": "1234"})
    return c.post("/report", json={
        "description": desc, "location_type": "academics_block", "block_no": "Block B",
        "floor": "2nd Floor", "room": "204", "photo_b64": "aGVsbG8=",
        "photo_mime": "image/jpeg"}).get_json()


def test_queue_lists_grievances(client):
    _report(client)
    _admin(client)
    data = client.get("/admin/grievances/data").get_json()
    assert len(data["rows"]) == 1
    assert data["rows"][0]["is_group"] is False


def test_queue_collapses_recurring_group(client):
    _report(client, "prof.rao")
    _report(client, "dr.iyer")
    _admin(client)
    rows = client.get("/admin/grievances/data").get_json()["rows"]
    assert len(rows) == 1
    assert rows[0]["is_group"] is True
    assert rows[0]["report_count"] == 2


def test_queue_status_filter(client):
    out = _report(client)
    _admin(client)
    g = grievances.get_by_code(out["code"])
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    assert len(client.get("/admin/grievances/data?status=verified").get_json()["rows"]) == 1
    assert client.get("/admin/grievances/data?status=closed").get_json()["rows"] == []
```

- [ ] **Step 5:** Run `pytest tests/test_admin_routes.py -q` → PASS (queue tests).

---

### Task 7: Grievance detail + workflow action routes

**Files:** Modify `blueprints/admin/__init__.py`; create `templates/admin/detail.html`
**Test:** `tests/test_admin_routes.py` (workflow portion)

**Interfaces:**
- `GET /admin/grievances/<code>` → detail: grievance, `timeline.list_for`, `evidence.list_for`, recurring group + members, allowed next statuses (`STATUS_TRANSITIONS[status]`), unit list, category list.
- POST actions (form posts, redirect back to detail; `@require_permission`):
  - `POST /admin/grievances/<code>/verify` → `transition(..., "verified")`
  - `POST /admin/grievances/<code>/category` (form `category`) → `correct_category`
  - `POST /admin/grievances/<code>/assign` (form `unit`, `assignee`) → `assign`
  - `POST /admin/grievances/<code>/status` (form `to`) → `transition`
  - `POST /admin/grievances/<code>/evidence` (form `kind`, `note`, file `photo`) → `add_resolution_evidence`
  - `POST /admin/grievances/<code>/note` (form `text`) → `add_note`
  - `POST /admin/grievances/<code>/reopen` (form `note`) → `reopen`
  - `WorkflowError` → re-render detail with an `error` banner (flash-style via query param `?err=`).

- [ ] **Step 1:** Add to `blueprints/admin/__init__.py`

```python
import base64

from flask import make_response

from db import evidence, timeline
from domain.constants import STATUS_TRANSITIONS
from domain.rbac import (GRIEVANCE_ASSIGN, GRIEVANCE_CHANGE_STATUS, GRIEVANCE_CLOSE,
                         GRIEVANCE_CORRECT_CATEGORY, GRIEVANCE_VERIFY,
                         GRIEVANCE_VERIFY_RESOLUTION, require_permission)


def _get_or_404(code):
    gr = grievances.get_by_code(code)
    if not gr:
        abort(404)
    return gr


@bp.get("/grievances/<code>")
def grievance_detail(code):
    gr = _get_or_404(code)
    group = recurring.get(gr["recurring_group_id"]) if gr["recurring_group_id"] else None
    members = recurring.members(group["id"]) if group else []
    return render_template(
        "admin/detail.html", g=gr, timeline=timeline.list_for(gr["id"]),
        evidence=evidence.list_for(gr["id"]), group=group, members=members,
        next_statuses=STATUS_TRANSITIONS.get(gr["status"], []),
        units=RESPONSIBLE_UNITS_FLAT, categories=CATEGORIES,
        error=request.args.get("err"),
    )


def _back(code, err=None):
    url = f"/admin/grievances/{code}"
    return redirect(url + (f"?err={err}" if err else ""))


def _actor():
    return g.current_user["username"]


@bp.post("/grievances/<code>/verify")
@require_permission(GRIEVANCE_VERIFY)
def act_verify(code):
    gr = _get_or_404(code)
    try:
        grievance_service.transition(gr["id"], "verified", actor=_actor(), actor_role="admin")
    except grievance_service.WorkflowError as e:
        return _back(code, e.message)
    return _back(code)


@bp.post("/grievances/<code>/category")
@require_permission(GRIEVANCE_CORRECT_CATEGORY)
def act_category(code):
    gr = _get_or_404(code)
    try:
        grievance_service.correct_category(gr["id"],
                                           category=request.form.get("category", ""),
                                           actor=_actor())
    except grievance_service.WorkflowError as e:
        return _back(code, e.message)
    return _back(code)


@bp.post("/grievances/<code>/assign")
@require_permission(GRIEVANCE_ASSIGN)
def act_assign(code):
    gr = _get_or_404(code)
    try:
        grievance_service.assign(gr["id"], unit=request.form.get("unit", ""),
                                 assignee=request.form.get("assignee", "").strip(),
                                 actor=_actor())
    except grievance_service.WorkflowError as e:
        return _back(code, e.message)
    return _back(code)


@bp.post("/grievances/<code>/status")
@require_permission(GRIEVANCE_CHANGE_STATUS)
def act_status(code):
    gr = _get_or_404(code)
    to = request.form.get("to", "")
    perm_ok = True
    if to == "admin_verified":
        from domain.rbac import has_permission
        perm_ok = has_permission(g.current_user["role"], GRIEVANCE_VERIFY_RESOLUTION)
    if to == "closed":
        from domain.rbac import has_permission
        perm_ok = has_permission(g.current_user["role"], GRIEVANCE_CLOSE)
    if not perm_ok:
        return _back(code, "Not allowed")
    try:
        grievance_service.transition(gr["id"], to, actor=_actor(), actor_role="admin",
                                     note=request.form.get("note") or None)
    except grievance_service.WorkflowError as e:
        return _back(code, e.message)
    return _back(code)


@bp.post("/grievances/<code>/evidence")
@require_permission(GRIEVANCE_CHANGE_STATUS)
def act_evidence(code):
    gr = _get_or_404(code)
    f = request.files.get("photo")
    b64 = base64.b64encode(f.read()).decode() if f and f.filename else ""
    mime = (f.mimetype if f else "image/jpeg") or "image/jpeg"
    try:
        grievance_service.add_resolution_evidence(
            gr["id"], kind=request.form.get("kind", "resolution_after"),
            image_b64=b64, mime=mime, note=request.form.get("note", "").strip(),
            actor=_actor())
    except grievance_service.WorkflowError as e:
        return _back(code, e.message)
    return _back(code)


@bp.post("/grievances/<code>/note")
@require_permission(GRIEVANCE_CHANGE_STATUS)
def act_note(code):
    gr = _get_or_404(code)
    grievance_service.add_note(gr["id"], actor=_actor(), actor_role="admin",
                               text=request.form.get("text", "").strip())
    return _back(code)


@bp.post("/grievances/<code>/reopen")
@require_permission(GRIEVANCE_CHANGE_STATUS)
def act_reopen(code):
    gr = _get_or_404(code)
    try:
        grievance_service.reopen(gr["id"], actor=_actor(),
                                 note=request.form.get("note") or None)
    except grievance_service.WorkflowError as e:
        return _back(code, e.message)
    return _back(code)
```

- [ ] **Step 2:** Write `templates/admin/detail.html`

```html
{% extends "base_admin.html" %}
{% block title %}{{ g.code }}{% endblock %}
{% block content %}
<h2>{{ g.code }} <span class="chip {{ g.status }}">{{ g.status.replace('_',' ') }}</span></h2>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<p class="muted">Priority <strong>{{ g.priority_score }}</strong> &middot;
  severity {{ g.severity or 'n/a' }} &middot; reporter {{ g.reporter_name }} &middot;
  {{ g.location_label }}</p>
{% if g.spam_flag %}<p class="error">Flagged as possible non-genuine report - review the photo.</p>{% endif %}

{% if g.primary_photo_url %}<img class="evidence" src="{{ g.primary_photo_url }}" style="max-width:320px">{% endif %}
<div class="card"><strong>Description</strong><p>{{ g.description }}</p>
  {% if g.ai_summary %}<p class="muted">AI: {{ g.ai_summary }}</p>{% endif %}</div>

{% if group %}
<div class="card"><strong>Recurring</strong> - {{ group.report_count }} reports from
  {{ group.reporter_count }} faculty. Members:
  {% for m in members %}<a href="/admin/grievances/{{ m.code }}">{{ m.code }}</a> {% endfor %}
</div>
{% endif %}

<div class="card">
  <strong>Category</strong>: {{ g.category or 'unclassified' }}
  {% if g.category_confirmed %}(confirmed){% endif %}
  {% if can('grievance.correct_category') %}
  <form method="post" action="/admin/grievances/{{ g.code }}/category" class="inline">
    <select name="category">{% for c in categories %}
      <option {{ 'selected' if c == g.category }}>{{ c }}</option>{% endfor %}</select>
    <button>Set category</button>
  </form>{% endif %}
</div>

{% if g.status == 'reported' and can('grievance.verify') %}
<form method="post" action="/admin/grievances/{{ g.code }}/verify"><button>Verify</button></form>
{% endif %}

{% if g.status == 'verified' and can('grievance.assign') %}
<div class="card"><strong>Assign to a Responsible Unit</strong>
  <form method="post" action="/admin/grievances/{{ g.code }}/assign">
    <select name="unit">{% for u in units %}<option>{{ u }}</option>{% endfor %}</select>
    <input name="assignee" placeholder="Person / team (optional)">
    <button>Assign (sets SLA due date)</button>
  </form>
</div>
{% endif %}

{% if g.responsible_unit %}
<div class="card"><strong>Assigned:</strong> {{ g.responsible_unit }}
  {% if g.assignee %}- {{ g.assignee }}{% endif %}
  {% if g.due_at %}<br>Due: {{ g.due_at | int }}{% endif %}</div>
{% endif %}

{% if g.status in ('in_progress',) and can('grievance.change_status') %}
<div class="card"><strong>Resolution evidence</strong>
  <form method="post" action="/admin/grievances/{{ g.code }}/evidence" enctype="multipart/form-data">
    <select name="kind"><option value="resolution_after">After photo</option>
      <option value="resolution_before">Before photo</option></select>
    <input type="file" name="photo" accept="image/*">
    <input name="note" placeholder="Resolution note (required for After)">
    <button>Upload evidence</button>
  </form>
</div>
{% endif %}

{% for e in evidence if e.kind != 'report' %}
<div class="card"><strong>{{ e.kind.replace('_',' ') }}</strong> - {{ e.note or '' }}
  <br><img class="evidence" src="/photo/{{ e.id }}" style="max-width:260px"></div>
{% endfor %}

{% if next_statuses and can('grievance.change_status') %}
<div class="card"><strong>Advance</strong>
  {% for s in next_statuses %}
  <form method="post" action="/admin/grievances/{{ g.code }}/status" class="inline">
    <input type="hidden" name="to" value="{{ s }}">
    <button>{{ 'Reopen' if s == 'in_progress' and g.status in ('resolved','admin_verified') else 'Mark ' + s.replace('_',' ') }}</button>
  </form>
  {% endfor %}
</div>
{% endif %}

<h3>Timeline</h3>
<ul class="timeline">
{% for e in timeline %}<li class="done">{{ e.event_type.replace('_',' ') }}
  {% if e.from_value %}{{ e.from_value }} &rarr; {% endif %}{{ e.to_value or '' }}
  <span class="muted">by {{ e.actor }}</span>
  {% if e.note %}<br><span class="muted">{{ e.note }}</span>{% endif %}</li>{% endfor %}
</ul>

<div class="card"><form method="post" action="/admin/grievances/{{ g.code }}/note">
  <input name="text" placeholder="Add an internal note"><button>Add note</button>
</form></div>
{% endblock %}
```

- [ ] **Step 3:** Add to `tests/test_admin_routes.py`

```python
def test_full_admin_workflow_via_routes(client):
    out = _report(client)
    _admin(client)
    code = out["code"]
    assert client.post(f"/admin/grievances/{code}/verify").status_code == 302
    r = client.post(f"/admin/grievances/{code}/assign",
                    data={"unit": "Infrastructure", "assignee": "Ravi"})
    assert r.status_code == 302
    client.post(f"/admin/grievances/{code}/status", data={"to": "in_progress"})

    # resolve is blocked without evidence
    client.post(f"/admin/grievances/{code}/status", data={"to": "resolved"})
    from db import grievances as gdb
    assert gdb.get_by_code(code)["status"] == "in_progress"

    # upload after-evidence + note, then resolve works
    import io
    client.post(f"/admin/grievances/{code}/evidence", data={
        "kind": "resolution_after", "note": "Fixed the fan",
        "photo": (io.BytesIO(b"img"), "after.jpg")},
        content_type="multipart/form-data")
    client.post(f"/admin/grievances/{code}/status", data={"to": "resolved"})
    assert gdb.get_by_code(code)["status"] == "resolved"
    client.post(f"/admin/grievances/{code}/status", data={"to": "admin_verified"})
    client.post(f"/admin/grievances/{code}/status", data={"to": "closed"})
    assert gdb.get_by_code(code)["status"] == "closed"


def test_detail_shows_error_on_bad_transition(client):
    out = _report(client)
    _admin(client)
    r = client.get(f"/admin/grievances/{out['code']}?err=Something+went+wrong")
    assert b"Something went wrong" in r.data


def test_faculty_cannot_post_admin_action(client):
    out = _report(client)
    client.post("/login", data={"username": "prof.rao", "pin": "1234"})
    assert client.post(f"/admin/grievances/{out['code']}/verify").status_code == 403
```

- [ ] **Step 4:** Run `pytest tests/test_admin_routes.py -q` → PASS.

---

### Task 8: Recurring, Notices, Users, Locations, Audit screens

**Files:** Modify `blueprints/admin/__init__.py`; create `templates/admin/{recurring,notices,users,locations,audit}.html`
**Test:** `tests/test_admin_routes.py` (CRUD portion)

**Interfaces:**
- `GET /admin/recurring` → active groups + members; `POST /admin/recurring/<gid>/resolve` → `recurring.set_status(gid, "resolved")` + audit (does NOT auto-resolve members — shows a hint).
- `GET/POST /admin/notices` — list + create (`title`, `body`, `publish` checkbox); `POST /admin/notices/<id>/publish` toggles.
- `GET/POST /admin/users` — list faculty + admins; create (`username`, `display_name`, `department`, `pin`, `role`); `POST /admin/users/<id>/toggle` (active); `POST /admin/users/<id>/pin` (reset). All → `audit.add`.
- `GET/POST /admin/locations` — list + create (`location_type` in `block|floor|subzone`, `name`, computed `full_path`); `POST /admin/locations/<id>/toggle`.
- `GET /admin/audit` → `audit.list_recent(300)`.
- All POST routes `@require_permission` with the matching permission.

- [ ] **Step 1:** Add to `blueprints/admin/__init__.py`

```python
from db import locations, notices, users
from domain.rbac import (AUDIT_VIEW, LOCATION_MANAGE, NOTICE_MANAGE, USER_MANAGE)
from services.auth_service import hash_pin


@bp.get("/recurring")
def recurring_page():
    groups = [{**gr, "members": recurring.members(gr["id"])}
              for gr in recurring.list_active()]
    return render_template("admin/recurring.html", groups=groups)


@bp.post("/recurring/<int:gid>/resolve")
@require_permission(GRIEVANCE_CHANGE_STATUS)
def recurring_resolve(gid):
    recurring.set_status(gid, "resolved")
    audit.add(_actor(), "recurring.resolve", target_type="recurring_group", target_id=gid)
    return redirect("/admin/recurring")


@bp.route("/notices", methods=["GET", "POST"])
@require_permission(NOTICE_MANAGE)
def notices_page():
    if request.method == "POST":
        n = notices.create(request.form["title"].strip(), request.form.get("body", "").strip(),
                           _actor(), is_published=bool(request.form.get("publish")))
        audit.add(_actor(), "notice.create", target_type="notice", target_id=n["id"])
        return redirect("/admin/notices")
    return render_template("admin/notices.html", notices=notices.list_all())


@bp.post("/notices/<int:nid>/publish")
@require_permission(NOTICE_MANAGE)
def notice_publish(nid):
    n = notices.get(nid)
    notices.publish(nid, not n["is_published"])
    audit.add(_actor(), "notice.publish", target_type="notice", target_id=nid)
    return redirect("/admin/notices")


@bp.route("/users", methods=["GET", "POST"])
@require_permission(USER_MANAGE)
def users_page():
    if request.method == "POST":
        try:
            u = users.create(request.form["username"].strip(),
                             request.form["display_name"].strip(),
                             request.form.get("role", "reporter"),
                             hash_pin(request.form["pin"].strip()),
                             department=request.form.get("department", "").strip() or None,
                             created_by=_actor())
            audit.add(_actor(), "user.create", target_type="user", target_id=u["id"])
        except ValueError as e:
            return render_template("admin/users.html", users=users.list_all(),
                                   error=str(e))
        return redirect("/admin/users")
    return render_template("admin/users.html", users=users.list_all(), error=None)


@bp.post("/users/<int:uid>/toggle")
@require_permission(USER_MANAGE)
def user_toggle(uid):
    u = users.get_by_id(uid)
    users.set_active(uid, not u["is_active"])
    audit.add(_actor(), "user.toggle", target_type="user", target_id=uid,
              detail={"active": not u["is_active"]})
    return redirect("/admin/users")


@bp.post("/users/<int:uid>/pin")
@require_permission(USER_MANAGE)
def user_pin(uid):
    users.set_pin(uid, hash_pin(request.form["pin"].strip()))
    audit.add(_actor(), "user.reset_pin", target_type="user", target_id=uid)
    return redirect("/admin/users")


@bp.route("/locations", methods=["GET", "POST"])
@require_permission(LOCATION_MANAGE)
def locations_page():
    if request.method == "POST":
        lt = request.form.get("location_type", "block")
        name = request.form["name"].strip()
        prefix = {"block": "Academics Block > ", "floor": "Academics Block > ",
                  "subzone": "Outer Area > "}.get(lt, "")
        try:
            loc = locations.create(lt, name, prefix + name)
            audit.add(_actor(), "location.create", target_type="location", target_id=loc["id"])
        except ValueError as e:
            return render_template("admin/locations.html",
                                   locations=locations.list_all(active_only=False), error=str(e))
        return redirect("/admin/locations")
    return render_template("admin/locations.html",
                           locations=locations.list_all(active_only=False), error=None)


@bp.post("/locations/<int:lid>/toggle")
@require_permission(LOCATION_MANAGE)
def location_toggle(lid):
    cur = next((l for l in locations.list_all(active_only=False) if l["id"] == lid), None)
    locations.set_active(lid, not cur["is_active"])
    return redirect("/admin/locations")


@bp.get("/audit")
@require_permission(AUDIT_VIEW)
def audit_page():
    return render_template("admin/audit.html", entries=audit.list_recent(300))
```

- [ ] **Step 2:** Write the 5 templates.

`templates/admin/recurring.html`:
```html
{% extends "base_admin.html" %}{% block title %}Recurring{% endblock %}{% block content %}
<h2>Recurring issues</h2>
{% for grp in groups %}
<div class="card" id="g{{ grp.id }}">
  <strong>{{ grp.title }}</strong> - {{ grp.report_count }} reports, {{ grp.reporter_count }} faculty
  <p class="muted">{{ grp.location_label }} &middot; {{ grp.category }}</p>
  {% for m in grp.members %}<a href="/admin/grievances/{{ m.code }}">{{ m.code }}</a>
    <span class="chip {{ m.status }}">{{ m.status.replace('_',' ') }}</span> {% endfor %}
  <form method="post" action="/admin/recurring/{{ grp.id }}/resolve" style="margin-top:8px">
    <button>Mark group resolved</button>
    <span class="muted">(resolve each member grievance separately)</span>
  </form>
</div>
{% else %}<p class="muted">No active recurring issues.</p>{% endfor %}
{% endblock %}
```

`templates/admin/notices.html`:
```html
{% extends "base_admin.html" %}{% block title %}Notices{% endblock %}{% block content %}
<h2>Campus notices</h2>
<div class="card"><form method="post" action="/admin/notices">
  <input name="title" placeholder="Title" required>
  <textarea name="body" rows="3" placeholder="Body"></textarea>
  <label><input type="checkbox" name="publish" value="1" style="width:auto"> Publish now</label>
  <button>Create notice</button>
</form></div>
<table class="grid"><thead><tr><th>Title</th><th>Status</th><th></th></tr></thead><tbody>
{% for n in notices %}<tr><td>{{ n.title }}</td>
  <td>{{ 'published' if n.is_published else 'draft' }}</td>
  <td><form method="post" action="/admin/notices/{{ n.id }}/publish" class="inline">
    <button>{{ 'Unpublish' if n.is_published else 'Publish' }}</button></form></td></tr>
{% endfor %}</tbody></table>
{% endblock %}
```

`templates/admin/users.html`:
```html
{% extends "base_admin.html" %}{% block title %}Faculty{% endblock %}{% block content %}
<h2>Accounts</h2>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<div class="card"><form method="post" action="/admin/users">
  <input name="username" placeholder="username" required>
  <input name="display_name" placeholder="Display name" required>
  <input name="department" placeholder="Department">
  <input name="pin" placeholder="Initial PIN" required>
  <select name="role"><option value="reporter">Faculty (reporter)</option>
    <option value="admin">Admin</option></select>
  <button>Create account</button>
</form></div>
<table class="grid"><thead><tr><th>Username</th><th>Name</th><th>Role</th><th>Dept</th>
  <th>Active</th><th></th></tr></thead><tbody>
{% for u in users %}<tr>
  <td>{{ u.username }}</td><td>{{ u.display_name }}</td><td>{{ u.role }}</td>
  <td>{{ u.department or '-' }}</td><td>{{ 'yes' if u.is_active else 'no' }}</td>
  <td>
    <form method="post" action="/admin/users/{{ u.id }}/toggle" class="inline">
      <button>{{ 'Deactivate' if u.is_active else 'Activate' }}</button></form>
    <form method="post" action="/admin/users/{{ u.id }}/pin" class="inline">
      <input name="pin" placeholder="new PIN" style="width:90px"><button>Reset</button></form>
  </td></tr>{% endfor %}
</tbody></table>
{% endblock %}
```

`templates/admin/locations.html`:
```html
{% extends "base_admin.html" %}{% block title %}Locations{% endblock %}{% block content %}
<h2>Campus locations</h2>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<div class="card"><form method="post" action="/admin/locations">
  <select name="location_type"><option value="block">Academics block</option>
    <option value="floor">Academics floor</option>
    <option value="subzone">Outer Area sub-zone</option></select>
  <input name="name" placeholder="Name e.g. Block E" required>
  <button>Add</button>
</form></div>
<table class="grid"><thead><tr><th>Type</th><th>Name</th><th>Path</th><th>Active</th><th></th></tr></thead><tbody>
{% for l in locations %}<tr><td>{{ l.location_type }}</td><td>{{ l.name }}</td>
  <td class="muted">{{ l.full_path }}</td><td>{{ 'yes' if l.is_active else 'no' }}</td>
  <td><form method="post" action="/admin/locations/{{ l.id }}/toggle" class="inline">
    <button>{{ 'Disable' if l.is_active else 'Enable' }}</button></form></td></tr>{% endfor %}
</tbody></table>
{% endblock %}
```

`templates/admin/audit.html`:
```html
{% extends "base_admin.html" %}{% block title %}Audit{% endblock %}{% block content %}
<h2>Audit log</h2>
<table class="grid"><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th></tr></thead><tbody>
{% for e in entries %}<tr><td class="muted">{{ e.created_at | int }}</td>
  <td>{{ e.actor }}</td><td>{{ e.action }}</td>
  <td>{{ e.target_type or '' }} {{ e.target_id or '' }}</td></tr>{% endfor %}
</tbody></table>
{% endblock %}
```

- [ ] **Step 3:** Add to `tests/test_admin_routes.py`

```python
def test_notice_crud(client):
    _admin(client)
    client.post("/admin/notices", data={"title": "Lift maintenance", "body": "Block A lift down",
                                        "publish": "1"})
    from db import notices
    assert any(n["title"] == "Lift maintenance" for n in notices.list_published())


def test_user_create_and_toggle(client):
    _admin(client)
    client.post("/admin/users", data={"username": "prof.new", "display_name": "Prof New",
                                      "department": "IT", "pin": "4321", "role": "reporter"})
    from db import users
    u = users.get_by_username("prof.new")
    assert u and u["is_active"]
    client.post(f"/admin/users/{u['id']}/toggle")
    assert users.get_by_id(u["id"])["is_active"] is False
    # the deactivated faculty cannot log in
    bad = client.application.test_client().post("/login",
            data={"username": "prof.new", "pin": "4321"})
    assert bad.status_code == 401


def test_location_add(client):
    _admin(client)
    client.post("/admin/locations", data={"location_type": "block", "name": "Block E"})
    from db import locations
    assert "Block E" in locations.picker()["academics_blocks"]


def test_audit_page_lists_actions(client):
    out = _report(client)
    _admin(client)
    client.post(f"/admin/grievances/{out['code']}/verify")
    r = client.get("/admin/audit")
    assert b"grievance.status" in r.data
```

- [ ] **Step 4:** Run `pytest tests/test_admin_routes.py -q` → PASS.

---

## Phase D — Intelligence layer

### Task 9: `intelligence_service.pulse()`

**Files:** Modify `services/intelligence_service.py`
**Test:** `tests/test_intelligence.py` (pulse portion)

**Interfaces:**
- `pulse() -> list[dict]` — one entry per `PULSE_DOMAINS` item:
  `{key, name, score (0-100, higher = healthier), open_count, high_open, recurring_count, avg_age_days, factors: list[str], trend: "up"|"down"|"flat"}`
  - domain match: `category in domain["categories"]` OR (`domain["location_type"]` and `g["location_type"] == it`) OR (`domain["sub_zone"]` and `g["sub_zone"] == it`)
  - `open_count` = matched grievances with status not in `_DONE`
  - `high_open` = those with severity `high`
  - `recurring_count` = active recurring groups whose `category` is in the domain's categories (or 0 for the location-only domains)
  - `avg_age_days` = mean of `(now - created_at)/86400` over open matched (0 if none)
  - `score = clamp(0..100, 100 - min(40, 4*open_count) - min(25, 6*high_open) - min(24, 8*recurring_count) - min(15, int(avg_age_days)))`
  - `factors` = the subtracted components (label + amount) sorted desc, top 2, e.g. `"12 open issues (-40)"`
  - `trend`: `"down"` (worsening) if open matched grievances created in the last 15 days > those created in the 15 days before that; `"up"` if fewer; else `"flat"`.

- [ ] **Step 1:** Add pulse test to `tests/test_intelligence.py`

```python
def test_pulse_all_healthy_when_empty(memstore):
    for d in si.pulse():
        assert d["score"] == 100
        assert d["open_count"] == 0


def test_pulse_electrical_drops_with_open_high_severity(memstore):
    for i in range(3):
        _g(memstore, category="Electric", severity="high", status="reported")
    dom = {d["key"]: d for d in si.pulse()}["electrical"]
    assert dom["open_count"] == 3
    assert dom["high_open"] == 3
    # 100 - min(40,12) - min(25,18) - 0 - 0 = 100 - 12 - 18 = 70
    assert dom["score"] == 70
    assert dom["factors"]


def test_pulse_domain_matches_by_location_type(memstore):
    _g(memstore, category="Plumbing", location_type="academics_block", status="reported")
    classrooms = {d["key"]: d for d in si.pulse()}["classrooms"]
    assert classrooms["open_count"] == 1
```

- [ ] **Step 2:** Add to `services/intelligence_service.py`

```python
from domain.constants import PULSE_DOMAINS

_DAY = 86400.0


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
```

- [ ] **Step 3:** Run `pytest tests/test_intelligence.py -q` → PASS.

---

### Task 10: `intelligence_service.gaps()`

**Files:** Modify `services/intelligence_service.py`
**Test:** `tests/test_intelligence.py` (gaps portion)

**Interfaces:**
- `gaps() -> list[dict]` — for each `(bucket, category)` over **non-closed** grievances where count `>= GAP_THRESHOLD`:
  `{location, category, count, recurring_count, recommended_action}`.
  - `bucket`: `block_no` if `location_type == "academics_block"` and `block_no` else `sub_zone` if `location_type == "outer_area"` and `sub_zone` else the location-type display name.
  - `recurring_count`: members of that bucket+category that have a `recurring_group_id`.
  - `recommended_action`: from `ACTION_TEMPLATES[category]`.
  - sorted by `count + 2*recurring_count` desc.

- [ ] **Step 1:** Add gaps test

```python
def test_gaps_surfaces_bucket_over_threshold(memstore):
    for i in range(4):
        _g(memstore, category="Electric", location_type="academics_block", block_no="Block B",
           location_label="Academics Block > Block B > 1st Floor > Room 1", status="reported")
    _g(memstore, category="Electric", location_type="academics_block", block_no="Block C",
       status="reported")   # below threshold, different bucket
    gaps = si.gaps()
    assert len(gaps) == 1
    assert gaps[0]["location"] == "Block B"
    assert gaps[0]["category"] == "Electric"
    assert gaps[0]["count"] == 4
    assert gaps[0]["recommended_action"]
```

- [ ] **Step 2:** Add to `services/intelligence_service.py`

```python
from collections import defaultdict

from domain.constants import GAP_THRESHOLD, LOCATION_TYPES

_TYPE_NAMES = {t["key"]: t["name"] for t in LOCATION_TYPES}
ACTION_TEMPLATES = {
    "Electric":     "Inspect and service the electrical fittings and wiring in this area.",
    "Power":        "Check the distribution board / backup supply feeding this area.",
    "Plumbing":     "Survey the plumbing lines here for recurring leaks or blockages.",
    "Civil":        "Schedule a structural / civil inspection and planned repair for this area.",
    "Mechanical":   "Have the AC / lift / pump equipment in this area serviced by the OEM.",
    "IT / Network": "Audit the network drops and AV equipment for this area.",
}


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
            "recommended_action": ACTION_TEMPLATES.get(cat, "Investigate the recurring problem in this area."),
        })
    out.sort(key=lambda r: -(r["count"] + 2 * r["recurring_count"]))
    return out
```

- [ ] **Step 3:** Run `pytest tests/test_intelligence.py -q` → PASS.

---

### Task 11: Pulse + Gaps admin screens + dashboard Pulse strip

**Files:** Modify `blueprints/admin/__init__.py`, `templates/admin/dashboard.html`; create `templates/admin/pulse.html`, `templates/admin/gaps.html`
**Test:** `tests/test_admin_routes.py`

**Interfaces:**
- `GET /admin/pulse` (`@require_permission(ANALYTICS_VIEW)`) → `pulse.html` with `intelligence_service.pulse()`.
- `GET /admin/gaps` (`@require_permission(ANALYTICS_VIEW)`) → `gaps.html` with `intelligence_service.gaps()`.
- Dashboard passes `pulse=intelligence_service.pulse()` and renders a compact strip.

- [ ] **Step 1:** Add routes to `blueprints/admin/__init__.py`

```python
from domain.rbac import ANALYTICS_VIEW


@bp.get("/pulse")
@require_permission(ANALYTICS_VIEW)
def pulse_page():
    return render_template("admin/pulse.html", domains=intelligence_service.pulse())


@bp.get("/gaps")
@require_permission(ANALYTICS_VIEW)
def gaps_page():
    return render_template("admin/gaps.html", gaps=intelligence_service.gaps())
```

- [ ] **Step 2:** In the `dashboard` view, add `pulse=intelligence_service.pulse()` to the `render_template` call.

- [ ] **Step 3:** Write `templates/admin/pulse.html`

```html
{% extends "base_admin.html" %}{% block title %}Pulse{% endblock %}{% block content %}
<h2>Infrastructure Pulse</h2>
<p class="muted">An operational indicator (0-100, higher is healthier) derived from open
  issues, severity, recurrence and age - not a scientific measurement.</p>
{% for d in domains %}
<div class="card">
  <strong>{{ d.name }}</strong> - <strong>{{ d.score }}</strong>/100
  <span class="muted">({{ d.trend }})</span>
  <div class="bar"><span style="width:{{ d.score }}%"></span></div>
  <p class="muted">{{ d.open_count }} open &middot; {{ d.high_open }} high-severity
    &middot; {{ d.recurring_count }} recurring &middot; avg age {{ d.avg_age_days }}d</p>
  {% if d.factors %}<p class="muted">Pressure: {{ d.factors | join(', ') }}</p>{% endif %}
</div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4:** Write `templates/admin/gaps.html`

```html
{% extends "base_admin.html" %}{% block title %}Gaps{% endblock %}{% block content %}
<h2>Infrastructure Gap Intelligence</h2>
<p class="muted">Areas where enough grievances have accumulated to point at an
  underlying problem worth a planned fix.</p>
{% for gp in gaps %}
<div class="card">
  <strong>{{ gp.location }} - {{ gp.category }}</strong>:
  {{ gp.count }} issues{% if gp.recurring_count %}, {{ gp.recurring_count }} recurring{% endif %}
  <p>&rarr; {{ gp.recommended_action }}</p>
</div>
{% else %}<p class="muted">No gaps yet - need at least {{ 4 }} grievances in one area+category.</p>{% endfor %}
{% endblock %}
```

- [ ] **Step 5:** Add the Pulse strip to `templates/admin/dashboard.html` (after the kpi-row):

```html
<h3>Infrastructure Pulse</h3>
<div class="kpi-row">
{% for d in pulse %}
  <div class="kpi"><b>{{ d.score }}</b>{{ d.name }}
    <div class="bar"><span style="width:{{ d.score }}%"></span></div></div>
{% endfor %}
</div>
```

- [ ] **Step 6:** Add to `tests/test_admin_routes.py`

```python
def test_pulse_and_gaps_pages(client):
    _admin(client)
    assert client.get("/admin/pulse").status_code == 200
    assert client.get("/admin/gaps").status_code == 200


def test_dashboard_shows_pulse_strip(client):
    _admin(client)
    r = client.get("/admin")
    assert b"Infrastructure Pulse" in r.data


def test_faculty_blocked_from_pulse(client):
    client.post("/login", data={"username": "prof.rao", "pin": "1234"})
    assert client.get("/admin/pulse").status_code == 403
```

- [ ] **Step 7:** Run `pytest tests/test_admin_routes.py -q` → PASS.

---

### Task 12: Full green + wrap-up

- [ ] **Step 1:** Clear caches, run everything:

```bash
cd "C:/Users/rocky/OneDrive/Desktop/unipulse/unipulse-campus"
rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache tests/__pycache__
python -m pytest -q
```
Expected: all pass (Phase 0/A/B's 87 + Phase C/D's ~35).

- [ ] **Step 2:** Compile check:

```bash
python -m compileall -q app.py wsgi.py config.py db domain services blueprints ai
```
Expected: exit 0.

- [ ] **Step 3:** End-to-end admin walkthrough:

```bash
python -c "
from app import create_app
app = create_app()
fac = app.test_client(); fac.post('/login', data={'username':'prof.rao','pin':'1234'})
out = fac.post('/report', json={'description':'the ceiling fan has stopped working in this room',
  'location_type':'academics_block','block_no':'Block B','floor':'2nd Floor','room':'204',
  'photo_b64':'aGVsbG8=','photo_mime':'image/jpeg'}).get_json()
code = out['code']
ad = app.test_client(); ad.post('/login', data={'username':'admin','pin':'0000'})
print('dashboard:', ad.get('/admin').status_code)
print('queue rows:', len(ad.get('/admin/grievances/data').get_json()['rows']))
ad.post(f'/admin/grievances/{code}/verify')
ad.post(f'/admin/grievances/{code}/assign', data={'unit':'Infrastructure','assignee':'Ravi'})
ad.post(f'/admin/grievances/{code}/status', data={'to':'in_progress'})
import io
ad.post(f'/admin/grievances/{code}/evidence', data={'kind':'resolution_after','note':'Replaced capacitor',
  'photo':(io.BytesIO(b'x'),'a.jpg')}, content_type='multipart/form-data')
ad.post(f'/admin/grievances/{code}/status', data={'to':'resolved'})
ad.post(f'/admin/grievances/{code}/status', data={'to':'admin_verified'})
ad.post(f'/admin/grievances/{code}/status', data={'to':'closed'})
from db import grievances
print('final status:', grievances.get_by_code(code)['status'])
print('pulse:', ad.get('/admin/pulse').status_code, '| gaps:', ad.get('/admin/gaps').status_code)
print('audit has entries:', b'grievance.assign' in ad.get('/admin/audit').data)
" 2>&1 | grep -v "storage_service\|\[db\]"
```
Expected: `dashboard: 200`, `queue rows: 1`, `final status: closed`, `pulse: 200 | gaps: 200`, `audit has entries: True`.

- [ ] **Step 4:** Update the memory note — Phases C+D done, Phase E next.

---

## Self-Review

**Spec coverage (C + D):**
- §5 `intelligence_service` (kpis/pulse/gaps) → Tasks 4, 9, 10. ✅
- §6 RBAC on every admin route (`@require_permission` + blueprint guard) → Tasks 5-11. ✅
- §9 priority recompute hooks → Task 2 (`recompute_priority` in every transition/assign/category) + Task 6 (`recompute_open` on queue load). ✅
- §10 Pulse (6 domains, score+trend+factors) → Task 9; Gap Intelligence (bucket+category ≥ threshold, recommended action) → Task 10; screens → Task 11. ✅
- §12 C: dashboard KPIs (Task 5), queue w/ filters+sort+search+recurring collapse (Task 6), detail + verify/category/assign+SLA/status/evidence/verify-resolution/close/reopen, gated + audited (Task 7), verified-resolution gate (Tasks 2-3), recurring screen + notices/users/locations CRUD + audit log (Task 8). ✅
- §12 D: priority-ranked queue default (Task 6, `sort="priority"` default in `list_query`), spam soft-flag surfaced (Task 1 column + Task 7 detail banner). ✅
- Deferred to Phase E (correctly not here): `/admin/analytics` + CSV export, Resend email, PWA polish, demo-data script. ✅

**Placeholder scan:** none — every code/test step is complete.

**Type consistency:**
- `grievance_service.transition(gid, to_status, *, actor, actor_role, note=None)` / `assign(gid, *, unit, assignee, actor, due_at=None)` / `correct_category(gid, *, category, actor)` / `add_resolution_evidence(gid, *, kind, image_b64, mime, note, actor)` / `reopen(gid, *, actor, note=None)` / `add_note(gid, *, actor, actor_role, text)` / `recompute_priority(gid)` / `recompute_open()` — signatures defined in Task 2, consumed identically in Tasks 3, 6, 7. ✅
- `WorkflowError.message` — set in Task 2, read in Tasks 3, 7. ✅
- `intelligence_service.kpis() -> {total,open,in_progress,resolved,sla_breaches,recurring}` (Task 4) — consumed in Task 5 dashboard template with those exact keys. ✅
- `intelligence_service.pulse()` entry keys `{key,name,score,open_count,high_open,recurring_count,avg_age_days,factors,trend}` (Task 9) — consumed in Task 11 `pulse.html` + dashboard strip. ✅
- `intelligence_service.gaps()` entry keys `{location,category,count,recurring_count,recommended_action}` (Task 10) — consumed in Task 11 `gaps.html`. ✅
- `db.recurring.members(group_id)` (Task 2) — used in Tasks 7, 8. ✅
- queue `/data` row shape (Task 6) — consumed in `admin_queue.js` (Task 6) with matching keys (`is_group`, `group_id`, `code`, `priority_score`, `report_count`, `status`, `overdue`, `due_at`). ✅
- `require_permission` + permission constants from `domain/rbac.py` (Phase 0/A) — imported and applied in Tasks 7, 8, 11. ✅
- `grievances.insert(**)` gains `spam_flag` (Task 1) — set in `grievance_service.submit` (Task 1 step 3). ✅

No issues found.
