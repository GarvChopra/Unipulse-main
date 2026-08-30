"""Auth blueprint: login / logout / token refresh."""
from flask import Blueprint, g, make_response, redirect, render_template, request, url_for

from config import Config
from services import auth_service

bp = Blueprint("auth", __name__, template_folder="../../templates")

_ACCESS, _REFRESH = "up_access", "up_refresh"
_SECURE = Config.is_production()


def _set_cookies(resp, access: str, refresh: str, remember: bool = False):
    resp.set_cookie(_ACCESS, access, max_age=15 * 60, httponly=True,
                    samesite="Strict", secure=_SECURE, path="/")
    resp.set_cookie(_REFRESH, refresh, max_age=(30 if remember else 7) * 24 * 3600,
                    httponly=True, samesite="Strict", secure=_SECURE, path="/auth/refresh")
    return resp


def _clear_cookies(resp):
    resp.set_cookie(_ACCESS, "", expires=0, path="/")
    resp.set_cookie(_REFRESH, "", expires=0, path="/auth/refresh")
    return resp


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if g.get("current_user"):
            return redirect("/admin" if g.current_user["role"] == "admin" else "/")
        return render_template("login.html", error=None)

    username = (request.form.get("username") or "").strip()
    pin = (request.form.get("pin") or "").strip()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if not auth_service.check_rate_limit(f"{username.lower()}@{ip}"):
        return render_template("login.html", error="Too many attempts - wait a few minutes."), 429

    result = auth_service.login(username, pin)
    if not result.success:
        return render_template("login.html", error=result.error), 401

    remember = bool(request.form.get("remember"))
    if remember:
        result.refresh_token = auth_service.create_refresh_token(result.user["username"], days=30)

    target = "/admin" if result.user["role"] == "admin" else "/"
    resp = make_response(redirect(target))
    return _set_cookies(resp, result.access_token, result.refresh_token, remember=remember)


@bp.get("/logout")
def logout():
    return _clear_cookies(make_response(redirect(url_for("auth.login"))))


@bp.post("/auth/refresh")
def refresh():
    tok = request.cookies.get(_REFRESH)
    if not tok:
        return {"error": "no refresh token"}, 401
    try:
        result = auth_service.refresh(tok)
    except auth_service.AuthError as e:
        return _clear_cookies(make_response({"error": str(e)}, 401))
    if not result.success:
        return _clear_cookies(make_response({"error": result.error}, 401))
    resp = make_response({"ok": True, "role": result.user["role"]})
    return _set_cookies(resp, result.access_token, result.refresh_token)
