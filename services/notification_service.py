"""Resend email notifications. Degrades to a silent no-op without RESEND_API_KEY."""
from __future__ import annotations

import requests

from config import Config
from domain.constants import GLB

_URL = "https://api.resend.com/emails"
_TIMEOUT = 10
_NOOP = {"sent": False, "reason": "not_configured"}


def is_available() -> bool:
    return bool(Config.RESEND_API_KEY)


def _deliver(to: str, subject: str, html: str) -> dict:
    resp = requests.post(
        _URL, timeout=_TIMEOUT,
        headers={"Authorization": f"Bearer {Config.RESEND_API_KEY}",
                 "Content-Type": "application/json"},
        json={"from": Config.RESEND_FROM, "to": [to], "subject": subject, "html": html},
    )
    resp.raise_for_status()
    return {"sent": True, "reason": "ok"}


def _safe(to, subject, html) -> dict:
    if not is_available():
        return dict(_NOOP)
    if not to:
        return {"sent": False, "reason": "no_recipient"}
    try:
        return _deliver(to, subject, html)
    except Exception as e:  # noqa: BLE001
        print(f"[notification_service] delivery failed: {type(e).__name__}: {e}")
        return {"sent": False, "reason": f"{type(e).__name__}: {e}"}


def notify_status_change(grievance: dict, new_status: str,
                         reporter_contact: str | None) -> dict:
    code = grievance.get("code", "your grievance")
    label = grievance.get("location_label", "")
    pretty = new_status.replace("_", " ")
    html = (f"<p>Your report <strong>{code}</strong> ({label}) is now "
            f"<strong>{pretty}</strong>.</p>"
            f"<p>Track it in {GLB['product']}.</p>")
    return _safe(reporter_contact, f"[{GLB['product']}] {code} is now {pretty}", html)


def notify_new_high_priority(grievance: dict) -> dict:
    code = grievance.get("code", "?")
    html = (f"<p>New high-priority grievance <strong>{code}</strong>.</p>"
            f"<p>Category: {grievance.get('category') or 'unclassified'} &middot; "
            f"priority {grievance.get('priority_score', 0)} &middot; "
            f"{grievance.get('location_label', '')}</p>")
    return _safe(Config.ADMIN_ALERT_EMAIL,
                 f"[{GLB['product']}] High-priority: {code}", html)
