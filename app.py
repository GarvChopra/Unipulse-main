"""UniPulse - GL Bajaj campus infrastructure intelligence. Flask app factory."""
import os

from flask import Flask, g, request

from config import Config
from domain.constants import GLB
from services import auth_service


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    from db import pool
    pool.init_db()

    from db import seeds
    seeds.run()

    from blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from blueprints.faculty import bp as faculty_bp
    app.register_blueprint(faculty_bp)

    from blueprints.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    @app.before_request
    def _load_user():
        g.current_user = None
        token = request.cookies.get("up_access")
        if not token:
            return
        try:
            p = auth_service.decode_access_token(token)
            g.current_user = {"username": p["sub"], "display_name": p.get("name", p["sub"]),
                              "role": p["role"], "department": p.get("dept")}
        except auth_service.AuthError:
            g.current_user = None

    @app.template_filter("when")
    def _when(ts):
        try:
            import time as _t
            return _t.strftime("%d %b %Y, %H:%M", _t.localtime(float(ts)))
        except Exception:
            return "—"

    @app.context_processor
    def _inject():
        from domain.rbac import has_permission
        user = g.get("current_user")
        bell_dot = False
        if user and user["role"] == "reporter":
            try:
                import time as _t
                from db import grievances as _gr, users as _u
                rec = _u.get_by_username(user["username"])
                if rec:
                    cut = _t.time() - 72 * 3600
                    bell_dot = any((r["updated_at"] or 0) >= cut and r["status"] != "reported"
                                   for r in _gr.list_for_reporter(rec["id"]))
            except Exception:
                bell_dot = False
        return {
            "current_user": user,
            "GLB": GLB,
            "bell_dot": bell_dot,
            "can": (lambda perm: bool(user) and has_permission(user["role"], perm)),
        }

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "db": pool.STATE["mode"]}

    return app


if __name__ == "__main__":
    _app = create_app()
    from db import pool
    if pool.is_memory() and os.environ.get("SEED_DEMO", "1") == "1":
        # in-memory dev run — load a realistic demo campus so the admin views are populated
        from scripts import seed_demo
        print("[demo]", seed_demo.build())
    _app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
             debug=os.environ.get("FLASK_DEBUG") == "1")
