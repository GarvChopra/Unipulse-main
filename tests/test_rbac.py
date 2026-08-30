from domain import rbac


def test_reporter_scope():
    assert rbac.has_permission("reporter", rbac.GRIEVANCE_CREATE)
    assert rbac.has_permission("reporter", rbac.GRIEVANCE_VIEW_OWN)
    assert not rbac.has_permission("reporter", rbac.GRIEVANCE_VIEW_ALL)
    assert not rbac.has_permission("reporter", rbac.GRIEVANCE_ASSIGN)


def test_admin_has_everything():
    everything = set().union(*rbac.ROLE_PERMISSIONS.values())
    for perm in everything:
        assert rbac.has_permission("admin", perm)


def test_unknown_role_or_none():
    assert not rbac.has_permission(None, rbac.GRIEVANCE_CREATE)
    assert not rbac.has_permission("ghost", rbac.GRIEVANCE_CREATE)


def test_require_permission_redirects_anonymous(app):
    from flask import Blueprint
    bp = Blueprint("t", __name__)

    @bp.get("/t/secret")
    @rbac.require_permission(rbac.GRIEVANCE_VIEW_ALL)
    def secret():
        return "ok"

    app.register_blueprint(bp)
    r = app.test_client().get("/t/secret")
    assert r.status_code in (301, 302)
    assert "/login" in r.headers["Location"]
