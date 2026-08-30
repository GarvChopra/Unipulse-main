"""Super Admin portal: dashboard, queue, workflow, recurring, pulse, gaps, CRUD, audit."""
import base64
import csv
import io as _io
import time as _time

from flask import Blueprint, Response, abort, g, redirect, render_template, request

from db import audit, evidence, grievances, locations, notices, recurring, timeline, users
from domain.constants import (CATEGORIES, LOCATION_TYPES, RESPONSIBLE_UNITS_FLAT,
                              STATUS_TRANSITIONS, STATUSES)
from domain.rbac import (ANALYTICS_VIEW, AUDIT_VIEW, GRIEVANCE_ASSIGN,
                         GRIEVANCE_CHANGE_STATUS, GRIEVANCE_CLOSE,
                         GRIEVANCE_CORRECT_CATEGORY, GRIEVANCE_VERIFY,
                         GRIEVANCE_VERIFY_RESOLUTION, LOCATION_MANAGE, NOTICE_MANAGE,
                         USER_MANAGE, has_permission, require_permission)
from services import grievance_service, intelligence_service
from services.auth_service import hash_pin

bp = Blueprint("admin", __name__, url_prefix="/admin",
               template_folder="../../templates")

_STATUS_RANK = {s: i for i, s in enumerate(STATUSES)}
_DONE = ("resolved", "admin_verified", "closed")


@bp.before_request
def _guard():
    if not g.get("current_user"):
        return redirect("/login")
    if g.current_user["role"] != "admin":
        abort(403)


def _actor():
    return g.current_user["username"]


def _get_or_404(code):
    gr = grievances.get_by_code(code)
    if not gr:
        abort(404)
    return gr


def _back(code, err=None):
    return redirect(f"/admin/grievances/{code}" + (f"?err={err}" if err else ""))


# ── dashboard ──────────────────────────────────────────────────────────────

@bp.get("/more")
def more_page():
    return render_template("admin/more.html")


@bp.get("/", strict_slashes=False)
def dashboard():
    return render_template(
        "admin/dashboard.html",
        kpis=intelligence_service.kpis(),
        pulse=intelligence_service.pulse(),
        overdue=intelligence_service.overdue(8),
        recurring=recurring.list_active()[:5],
        activity=audit.list_recent(10),
    )


# ── queue ──────────────────────────────────────────────────────────────────

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
    for gg in rows:
        gid = gg.get("recurring_group_id")
        (grouped.setdefault(gid, []).append(gg) if gid in active_groups else singles.append(gg))

    def _overdue(x):
        return bool(x["due_at"] and now > x["due_at"] and x["status"] not in _DONE)

    out = []
    for gg in singles:
        out.append({
            "code": gg["code"], "group_id": None, "title": gg["title"],
            "category": gg["category"], "status": gg["status"],
            "location_label": gg["location_label"], "priority_score": gg["priority_score"],
            "report_count": 1, "reporter_name": gg["reporter_name"],
            "due_at": gg["due_at"], "overdue": _overdue(gg), "is_group": False,
        })
    for gid, members in grouped.items():
        grp = active_groups[gid]
        lead = min(members, key=lambda m: _STATUS_RANK.get(m["status"], 0))
        out.append({
            "code": None, "group_id": gid, "title": grp["title"],
            "category": grp["category"], "status": lead["status"],
            "location_label": grp["location_label"],
            "priority_score": max(m["priority_score"] for m in members),
            "report_count": grp["report_count"],
            "reporter_name": f"{grp['reporter_count']} faculty",
            "due_at": lead["due_at"], "overdue": any(_overdue(m) for m in members),
            "is_group": True,
        })
    out.sort(key=lambda r: -r["priority_score"])
    return {"rows": out}


# ── detail + workflow actions ─────────────────────────────────────────────

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
    role = g.current_user["role"]
    if to == "admin_verified" and not has_permission(role, GRIEVANCE_VERIFY_RESOLUTION):
        return _back(code, "Not allowed")
    if to == "closed" and not has_permission(role, GRIEVANCE_CLOSE):
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


# ── recurring ──────────────────────────────────────────────────────────────

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


# ── pulse + gaps ──────────────────────────────────────────────────────────

@bp.get("/pulse")
@require_permission(ANALYTICS_VIEW)
def pulse_page():
    return render_template("admin/pulse.html", domains=intelligence_service.pulse(),
                           overall=intelligence_service.overall_health())


@bp.get("/gaps")
@require_permission(ANALYTICS_VIEW)
def gaps_page():
    return render_template("admin/gaps.html", gaps=intelligence_service.gaps())


@bp.get("/analytics")
@require_permission(ANALYTICS_VIEW)
def analytics_page():
    return render_template("admin/analytics.html", a=intelligence_service.analytics())


@bp.get("/analytics.csv")
@require_permission(ANALYTICS_VIEW)
def analytics_csv():
    cols = ["code", "category", "severity", "status", "priority_score", "location_label",
            "responsible_unit", "assignee", "created_at", "assigned_at", "due_at",
            "resolved_at", "closed_at", "recurring_group_id", "spam_flag"]
    buf = _io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for gr in grievances.list_query(limit=100000):
        w.writerow([gr.get(c) for c in cols])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=unipulse_grievances.csv"})


# ── notices CRUD ──────────────────────────────────────────────────────────

@bp.route("/notices", methods=["GET", "POST"])
@require_permission(NOTICE_MANAGE)
def notices_page():
    if request.method == "POST":
        n = notices.create(request.form["title"].strip(),
                           request.form.get("body", "").strip(), _actor(),
                           is_published=bool(request.form.get("publish")))
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


# ── users CRUD ────────────────────────────────────────────────────────────

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
            return render_template("admin/users.html", users=users.list_all(), error=str(e))
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


# ── locations CRUD ────────────────────────────────────────────────────────

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


# ── audit ─────────────────────────────────────────────────────────────────

@bp.get("/audit")
@require_permission(AUDIT_VIEW)
def audit_page():
    return render_template("admin/audit.html", entries=audit.list_recent(300))
