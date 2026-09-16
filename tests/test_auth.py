from tests.conftest import TEST_PASSWORD, login


def test_login_success(client, owner):
    resp = login(client, owner)
    assert resp.status_code == 200
    assert b"dashboard" in resp.request.path.encode() or resp.request.path == "/dashboard"


def test_login_wrong_password(client, owner):
    resp = client.post(
        "/auth/login",
        data={"email": owner.email, "password": "wrong-password"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Identifiants incorrects".encode() in resp.data


def test_login_lockout_after_max_attempts(client, owner, tenant):
    max_attempts = tenant.max_login_attempts
    for _ in range(max_attempts):
        client.post(
            "/auth/login",
            data={"email": owner.email, "password": "wrong-password"},
            follow_redirects=True,
        )
    resp = client.post(
        "/auth/login",
        data={"email": owner.email, "password": TEST_PASSWORD},
        follow_redirects=True,
    )
    assert "verrouill".encode() in resp.data


def test_inactive_user_cannot_login(app, client, worker):
    from app.extensions import db
    from app.utils.tenant import tenant_bypass

    with app.app_context():
        with tenant_bypass():
            u = db.session.get(type(worker), worker.id)
            u.is_active = False
            db.session.commit()

    resp = login(client, worker)
    assert "Identifiants incorrects".encode() in resp.data


def test_logout_requires_no_special_state(client, owner):
    login(client, owner)
    resp = client.get("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200
    # Apres deconnexion, une page proprietaire redirige vers le login.
    resp2 = client.get("/parametres", follow_redirects=False)
    assert resp2.status_code in (302, 401)
