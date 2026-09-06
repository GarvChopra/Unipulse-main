"""Unauthenticated pages required for Google Play: privacy policy, account
deletion information, and the Digital Asset Links file that verifies the TWA."""
import os

from flask import Blueprint, Response, current_app, render_template, send_from_directory

from domain.constants import GLB

bp = Blueprint("public", __name__, template_folder="../../templates")

CONTACT_EMAIL = os.environ.get("PRIVACY_CONTACT_EMAIL", "").strip() \
    or f"unifix@{GLB['email_domain']}"


@bp.get("/service-worker.js")
def service_worker():
    """Serve the service worker from the site root so its scope is '/' (a worker
    served from /static/ can only control /static/, which means Chrome never
    fires beforeinstallprompt on the app pages)."""
    resp = send_from_directory(current_app.static_folder, "service-worker.js",
                               mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.get("/get-app")
def get_app():
    """Standalone install page. Public (no login) so its URL can be shared as a
    QR code. 'Install instantly' fires the PWA beforeinstallprompt."""
    return render_template("public/get_app.html", contact=CONTACT_EMAIL, glb=GLB)


@bp.get("/privacy")
def privacy():
    return render_template("public/privacy.html", contact=CONTACT_EMAIL, glb=GLB)


@bp.get("/account-deletion")
def account_deletion():
    return render_template("public/account_deletion.html", contact=CONTACT_EMAIL, glb=GLB)


@bp.get("/.well-known/assetlinks.json")
def assetlinks():
    """Digital Asset Links — lets Chrome verify the Android TWA owns this origin
    so it launches without a URL bar. Populated from the app signing key's
    SHA-256 fingerprint(s)."""
    pkg = os.environ.get("TWA_PACKAGE_NAME", "in.ac.glbitm.unifix").strip()
    fps = [f.strip() for f in
           os.environ.get("TWA_SHA256_CERT_FINGERPRINTS", "").split(",") if f.strip()]
    body = [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": pkg,
                   "sha256_cert_fingerprints": fps},
    }]
    return Response(__import__("json").dumps(body, indent=2),
                    mimetype="application/json")
