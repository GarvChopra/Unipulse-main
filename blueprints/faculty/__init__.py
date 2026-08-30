"""Faculty PWA blueprint: home, report, my-reports, grievance detail, notices."""
import base64

from flask import Blueprint, Response, abort, g, redirect, render_template, request

from db import audit, evidence, grievances, locations, notices, recurring, timeline, users
from domain.constants import CATEGORIES, LOCATION_TYPES, STATUSES
from domain.models import build_location_label
from services import classification_service, grievance_service, intelligence_service
from services.auth_service import hash_pin, verify_pin

bp = Blueprint("faculty", __name__, template_folder="../../templates")

_TYPE_NAMES = {t["key"]: t["name"] for t in LOCATION_TYPES}
_STEP_LABELS = {
    "reported": "Reported", "verified": "Verified", "assigned": "Assigned",
    "in_progress": "In progress", "resolved": "Resolved",
    "admin_verified": "Admin verified", "closed": "Closed",
}


@bp.before_request
def _require_login():
    if request.path == "/offline":
        return
    if not g.get("current_user"):
        return redirect("/login")
    if g.current_user["role"] == "admin" and request.path == "/":
        return redirect("/admin")


@bp.get("/offline")
def offline_page():
    return render_template("faculty/offline.html")


def _uid():
    u = users.get_by_username(g.current_user["username"])
    return u["id"] if u else -1


# ── home / notices ──────────────────────────────────────────────────────────

@bp.get("/")
def home():
    mine = grievances.list_for_reporter(_uid())
    open_count = sum(1 for r in mine if r["status"] not in ("closed", "admin_verified"))
    published = notices.list_published()
    pk = {d["key"]: d for d in intelligence_service.pulse()}
    health = [{"name": "Electrical", "pct": pk["electrical"]["score"]},
              {"name": "Water", "pct": pk["water"]["score"]},
              {"name": "Cleanliness", "pct": pk["cleanliness"]["score"]}]
    return render_template("faculty/home.html", open_count=open_count,
                           recent=mine[:3], latest_notice=(published[0] if published else None),
                           campus_health=health, notice_count=len(published))


@bp.get("/profile")
def profile_page():
    u = users.get_by_username(g.current_user["username"])
    return render_template("faculty/profile.html", u=u,
                           ok=request.args.get("ok"), err=request.args.get("err"))


@bp.post("/profile/pin")
def profile_pin():
    u = users.get_by_username(g.current_user["username"])
    cur = (request.form.get("current") or "").strip()
    new = (request.form.get("new") or "").strip()
    if not verify_pin(cur, u["pin_hash"]):
        return redirect("/profile?err=Current+PIN+is+incorrect")
    if not (new.isdigit() and 4 <= len(new) <= 8):
        return redirect("/profile?err=New+PIN+must+be+4-8+digits")
    users.set_pin(u["id"], hash_pin(new))
    audit.add(u["username"], "user.self_pin", target_type="user", target_id=u["id"])
    return redirect("/profile?ok=1")


@bp.get("/notices")
def notices_page():
    return render_template("faculty/notices.html", notices=notices.list_published())


@bp.get("/photo/<int:eid>")
def photo(eid):
    all_ev = [e for gr in grievances.list_query(limit=100000)
              for e in evidence.list_for(gr["id"])]
    ev = next((e for e in all_ev if e["id"] == eid), None)
    if not ev:
        abort(404)
    gr = grievances.get_by_id(ev["grievance_id"])
    if g.current_user["role"] != "admin" and gr["reporter_id"] != _uid():
        abort(403)
    url = ev.get("image_url") or ""
    if url.startswith("http"):
        return redirect(url)
    if url.startswith("data:"):
        header, b64 = url.split(",", 1)
        mime = header.split(":", 1)[1].split(";", 1)[0]
        return Response(base64.b64decode(b64), mimetype=mime,
                        headers={"Cache-Control": "private, max-age=86400"})
    abort(404)


# ── report wizard ──────────────────────────────────────────────────────────

@bp.get("/report")
def report_page():
    return render_template("faculty/report.html", picker=locations.picker(),
                           type_names=_TYPE_NAMES, categories=CATEGORIES)


@bp.post("/report/analyze")
def report_analyze():
    d = request.get_json(silent=True) or {}
    res = classification_service.classify(
        (d.get("description") or "").strip(),
        photo_b64=d.get("photo_b64"), photo_mime=d.get("photo_mime", "image/jpeg"),
    )
    return {"ai_summary": res["ai_summary"], "category": res["category"],
            "severity": res["severity"], "spam_flag": res["spam_flag"],
            "source": res["source"]}


@bp.post("/report")
def report_submit():
    d = request.get_json(silent=True) or {}
    label = build_location_label(
        d.get("location_type"), d.get("block_no"), d.get("floor"),
        d.get("room"), d.get("sub_zone"), type_names=_TYPE_NAMES,
    )
    sub = {
        "reporter_id": _uid(),
        "description": (d.get("description") or "").strip(),
        "location_type": d.get("location_type"),
        "block_no": d.get("block_no"), "floor": d.get("floor"),
        "room": d.get("room"), "sub_zone": d.get("sub_zone"),
        "location_label": label,
        "photo_b64": d.get("photo_b64"), "photo_mime": d.get("photo_mime", "image/jpeg"),
        "category": d.get("category"),
        "severity": d.get("severity"),
        "noticed_at": d.get("noticed_at"),
        "affects_academics": bool(d.get("affects_academics")),
        "ai": d.get("ai"),
    }
    try:
        out = grievance_service.submit(sub)
    except grievance_service.SubmissionError as e:
        return {"errors": e.errors}, 400
    return {"code": out["code"], "recurring": out["recurring"]}


# ── my reports / detail ────────────────────────────────────────────────────

@bp.get("/my-reports")
def my_reports_page():
    return render_template("faculty/my_reports.html")


@bp.get("/my-reports/data")
def my_reports_data():
    rows = grievances.list_for_reporter(_uid())
    return {"grievances": [
        {"code": r["code"], "category": r["category"], "status": r["status"],
         "location_label": r["location_label"], "created_at": r["created_at"],
         "priority_score": r["priority_score"], "title": r["title"],
         "severity": r["severity"],
         "recurring_group_id": r["recurring_group_id"]}
        for r in rows
    ]}


@bp.get("/grievance/<code>")
def grievance_detail(code):
    gr = grievances.get_by_code(code)
    if not gr:
        abort(404)
    if g.current_user["role"] != "admin" and gr["reporter_id"] != _uid():
        abort(403)
    idx = STATUSES.index(gr["status"]) if gr["status"] in STATUSES else 0
    steps = [{"key": s, "label": _STEP_LABELS[s], "done": i < idx, "current": i == idx}
             for i, s in enumerate(STATUSES)]
    group = recurring.get(gr["recurring_group_id"]) if gr["recurring_group_id"] else None
    return render_template("faculty/grievance_detail.html", g=gr,
                           timeline=timeline.list_for(gr["id"]),
                           evidence=evidence.list_for(gr["id"]),
                           group=group, steps=steps)
