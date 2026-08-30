"""The faculty grievance submission pipeline."""
from __future__ import annotations

import time

from db import audit, evidence, grievances, recurring, timeline, users
from domain.constants import (CATEGORIES, HIGH_PRIORITY_ALERT, RESPONSIBLE_UNITS_FLAT,
                              SLA_HOURS, STATUS_TRANSITIONS)
from services import (classification_service, duplicate_service, notification_service,
                      storage_service)
from services.validation_service import validate_submission


class SubmissionError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _group_title(label: str, category: str) -> str:
    tail = label.split(" > ")[-1]
    return f"{tail} - {category}"


def submit(sub: dict) -> dict:
    # 1. validate
    errors = validate_submission(sub)
    if errors:
        raise SubmissionError(errors)

    reporter = users.get_by_id(sub["reporter_id"])
    reporter_name = reporter["display_name"] if reporter else "Unknown"
    description = sub["description"].strip()
    label = sub["location_label"].strip()

    # 2. classify (reuse the wizard's /report/analyze result if given)
    pre = sub.get("ai") or {}
    if pre.get("category") in CATEGORIES or pre.get("ai_summary"):
        cls = {
            "category": pre.get("category") if pre.get("category") in CATEGORIES else None,
            "severity": pre.get("severity", "medium"),
            "ai_summary": pre.get("ai_summary", description[:160]),
            "confidence": int(pre.get("confidence", 60) or 60),
            "spam_flag": bool(pre.get("spam_flag", False)),
            "source": "preview",
        }
    else:
        cls = classification_service.classify(
            description, photo_b64=sub.get("photo_b64"),
            photo_mime=sub.get("photo_mime", "image/jpeg"),
        )

    # the faculty's picks win over the AI/keyword guess when provided
    from domain.constants import SEVERITIES
    form_sev = sub.get("severity")
    severity = form_sev if form_sev in SEVERITIES else cls["severity"]
    form_cat = sub.get("category")
    category = form_cat if form_cat in CATEGORIES else cls["category"]
    affects = bool(sub.get("affects_academics"))

    # 3. recurring / duplicate
    dup = duplicate_service.find_recurring(label, category, sub["reporter_id"])
    if dup["same_reporter_recent"]:
        raise SubmissionError([
            "You already reported this exact issue in the last 24 hours. "
            "The admin can see it - no need to report it again."
        ])

    # 4. store photo
    photo_url = storage_service.upload_image(sub.get("photo_b64") or "",
                                             sub.get("photo_mime", "image/jpeg"))

    # 5. insert grievance
    g_seed = {
        "severity": severity, "category": category, "status": "reported",
        "created_at": time.time(), "location_type": sub["location_type"],
        "sub_zone": sub.get("sub_zone"), "affects_academics": affects,
    }
    priority = classification_service.priority_score(g_seed)

    title = cls["ai_summary"][:120] if cls["ai_summary"] else description[:120]
    g = grievances.insert(
        reporter_id=sub["reporter_id"], reporter_name=reporter_name,
        title=title, description=description,
        category=category, severity=severity,
        priority_score=priority,
        location_type=sub["location_type"], block_no=sub.get("block_no"),
        floor=sub.get("floor"), room=sub.get("room"), sub_zone=sub.get("sub_zone"),
        location_label=label,
        noticed_at=sub.get("noticed_at"), affects_academics=affects,
        ai_summary=cls["ai_summary"], ai_confidence=cls["confidence"],
        spam_flag=cls["spam_flag"],
    )

    # 6. report-photo evidence + backfill the served URL onto the grievance
    ev = evidence.add(g["id"], "report", image_url=photo_url,
                      thumbnail_url=photo_url, uploaded_by=reporter_name)
    served = f"/photo/{ev['id']}"
    grievances.update(g["id"], primary_photo_url=served, thumbnail_url=served)

    timeline.add(g["id"], "created", actor=reporter_name, actor_role="reporter",
                 note=f"Reported via {cls.get('source', 'form')}")

    # 7. recurring group
    recurring_out = None
    if dup["match"]:
        grp = recurring.find_active(label, category)
        first_partner = dup["candidates"][0]
        if grp is None:
            grp = recurring.create(label, category,
                                   _group_title(label, category),
                                   primary_grievance_id=first_partner["id"],
                                   first_ts=first_partner.get("created_at") or time.time())
            grievances.update(first_partner["id"], recurring_group_id=grp["id"])
            recurring.bump(grp["id"],
                           last_ts=first_partner.get("created_at") or time.time(),
                           add_reporter=True)
            timeline.add(first_partner["id"], "merged_recurring", actor="system",
                         to_value=grp["title"], note="Grouped as a recurring issue")

        prior_reporters = {c["reporter_id"] for c in dup["candidates"]}
        grievances.update(g["id"], recurring_group_id=grp["id"])
        grp = recurring.bump(grp["id"], last_ts=time.time(),
                             add_reporter=sub["reporter_id"] not in prior_reporters)
        timeline.add(g["id"], "merged_recurring", actor="system",
                     to_value=grp["title"], note="Grouped as a recurring issue")
        recurring_out = {"group_id": grp["id"], "report_count": grp["report_count"]}

    try:
        if priority >= HIGH_PRIORITY_ALERT or severity == "high":
            notification_service.notify_new_high_priority(grievances.get_by_id(g["id"]))
    except Exception as e:  # noqa: BLE001
        print(f"[grievance_service] high-priority alert failed: {e}")

    return {
        "code": g["code"], "grievance_id": g["id"], "category": category,
        "recurring": recurring_out, "spam_flag": cls["spam_flag"],
    }


# ── admin workflow ─────────────────────────────────────────────────────────

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

    now = time.time()
    patch = {"status": to_status}
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

    try:
        updated = grievances.get_by_id(gid)
        reporter = users.get_by_id(updated["reporter_id"]) if updated["reporter_id"] else None
        notification_service.notify_status_change(
            updated, to_status, reporter.get("contact") if reporter else None)
    except Exception as e:  # noqa: BLE001
        print(f"[grievance_service] status email failed: {e}")

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
