"""Role-based access control. Stdlib + flask only (decorator)."""
from __future__ import annotations

import functools

GRIEVANCE_CREATE            = "grievance.create"
GRIEVANCE_VIEW_OWN          = "grievance.view_own"
GRIEVANCE_VIEW_ALL          = "grievance.view_all"
GRIEVANCE_VERIFY            = "grievance.verify"
GRIEVANCE_CORRECT_CATEGORY  = "grievance.correct_category"
GRIEVANCE_ASSIGN            = "grievance.assign"
GRIEVANCE_CHANGE_STATUS     = "grievance.change_status"
GRIEVANCE_VERIFY_RESOLUTION = "grievance.verify_resolution"
GRIEVANCE_CLOSE             = "grievance.close"
ANALYTICS_VIEW             = "analytics.view"
NOTICE_MANAGE             = "notice.manage"
USER_MANAGE               = "user.manage"
LOCATION_MANAGE           = "location.manage"
AUDIT_VIEW                = "audit.view"

_REPORTER = {GRIEVANCE_CREATE, GRIEVANCE_VIEW_OWN}
_ADMIN = {
    GRIEVANCE_VIEW_ALL, GRIEVANCE_VERIFY, GRIEVANCE_CORRECT_CATEGORY, GRIEVANCE_ASSIGN,
    GRIEVANCE_CHANGE_STATUS, GRIEVANCE_VERIFY_RESOLUTION, GRIEVANCE_CLOSE,
    ANALYTICS_VIEW, NOTICE_MANAGE, USER_MANAGE, LOCATION_MANAGE, AUDIT_VIEW,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "reporter": set(_REPORTER),
    "admin": set(_REPORTER) | _ADMIN,
}


def has_permission(role, perm: str) -> bool:
    return bool(role) and perm in ROLE_PERMISSIONS.get(role, set())


def require_permission(perm: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import g, redirect, request, jsonify
            user = g.get("current_user")
            if user and has_permission(user["role"], perm):
                return fn(*args, **kwargs)
            wants_json = request.method != "GET" or request.path.endswith("/data") \
                or request.path.startswith("/api/")
            if wants_json:
                return jsonify({"error": "forbidden", "need": perm}), 403
            return redirect("/login")
        return wrapper
    return deco
