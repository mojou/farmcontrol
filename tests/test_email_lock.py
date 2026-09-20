"""Un compte proprietaire cree par inscription libre est bloque si l'email
n'est pas confirme dans les 3 heures ; le lien de confirmation le reactive."""
import uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.core import EmailVerificationToken, Tenant, User
from app.utils.tenant import tenant_bypass
from tests.conftest import TEST_PASSWORD, login


def _set(app, user, **fields):
    with app.app_context():
        with tenant_bypass():
            u = db.session.get(User, user.id)
            for k, v in fields.items():
                setattr(u, k, v)
            db.session.commit()


def _get(app, user):
    with app.app_context():
        with tenant_bypass():
            u = db.session.get(User, user.id)
            return u.email_verified_at, u.email_confirm_deadline


def _expire(app, user):
    """Simule '3 heures ecoulees sans confirmation'."""
    _set(app, user, email_verified_at=None, email_confirm_deadline=datetime.now(timezone.utc) - timedelta(minutes=1))


def _login_attempt(client, user):
    client.get("/auth/logout")
    return client.post("/auth/login", data={"email": user.email, "password": TEST_PASSWORD}, follow_redirects=True)


# ---------------------------------------------------------------- inscription

def test_signup_sets_a_three_hour_deadline(app, client, monkeypatch):
    sent = []
    monkeypatch.setattr("app.blueprints.auth.routes.send_welcome_email", lambda *a, **k: sent.append(k))
    email = f"inscrit-{uuid.uuid4().hex[:8]}@example.com"
    before = datetime.now(timezone.utc)
    try:
        client.post(
            "/auth/inscription",
            data={
                "organization_name": f"Ferme {uuid.uuid4().hex[:6]}", "first_name": "Test", "last_name": "Inscrit",
                "email": email, "password": TEST_PASSWORD, "password_confirm": TEST_PASSWORD, "accept_terms": "y",
            },
            follow_redirects=True,
        )
        with app.app_context():
            with tenant_bypass():
                user = User.query.filter_by(email=email).first()
                assert user is not None and user.email_verified_at is None
                delta = user.email_confirm_deadline - before
                assert timedelta(hours=2, minutes=59) <= delta <= timedelta(hours=3, minutes=1)
        assert sent  # le lien de confirmation part par email
        # compte utilisable pendant les 3 heures, avec le compte a rebours
        html = client.get("/dashboard").get_data(as_text=True)
        assert "votre compte sera bloque" in html
    finally:
        with app.app_context():
            with tenant_bypass():
                user = User.query.filter_by(email=email).first()
                if user is not None:
                    tenant = db.session.get(Tenant, user.tenant_id)
                    db.session.delete(tenant)
                    db.session.commit()


# ------------------------------------------------------------------ blocage

def test_account_is_usable_before_the_deadline(app, client, owner):
    _set(app, owner, email_verified_at=None, email_confirm_deadline=datetime.now(timezone.utc) + timedelta(hours=2))
    login(client, owner)
    assert client.get("/dashboard").status_code == 200
    html = client.get("/dashboard").get_data(as_text=True)
    assert "1 h 59 min" in html or "2 h 0 min" in html or "1 h 5" in html


def test_login_is_refused_after_the_deadline(app, client, owner):
    _expire(app, owner)
    resp = _login_attempt(client, owner)
    html = resp.get_data(as_text=True)
    assert "il est bloque" in html
    assert "Recevoir un nouveau lien de confirmation" in html
    assert client.get("/dashboard", follow_redirects=False).status_code == 302  # pas connecte


def test_open_session_is_cut_after_the_deadline(app, client, owner):
    _set(app, owner, email_verified_at=None, email_confirm_deadline=datetime.now(timezone.utc) + timedelta(hours=1))
    login(client, owner)
    assert client.get("/dashboard").status_code == 200
    _expire(app, owner)  # les 3 heures passent pendant que la session est ouverte
    resp = client.get("/dashboard", follow_redirects=True)
    assert "il est bloque" in resp.get_data(as_text=True)
    assert client.get("/elevage/lots", follow_redirects=False).status_code == 302


def test_wrong_password_does_not_reveal_the_block(app, client, owner):
    _expire(app, owner)
    client.get("/auth/logout")
    html = client.post("/auth/login", data={"email": owner.email, "password": "mauvais"}, follow_redirects=True).get_data(as_text=True)
    assert "Identifiants incorrects" in html and "il est bloque" not in html


def test_public_pages_stay_reachable_for_a_blocked_account(app, client, owner):
    _set(app, owner, email_verified_at=None, email_confirm_deadline=datetime.now(timezone.utc) + timedelta(hours=1))
    login(client, owner)
    _expire(app, owner)
    for url in ("/tarifs", "/contact", "/documentation", "/conditions-generales"):
        assert client.get(url).status_code == 200, url


# ----------------------------------------------------------------- reactivation

def test_new_link_then_confirmation_unblocks_the_account(app, client, owner, monkeypatch):
    sent = []
    monkeypatch.setattr("app.blueprints.auth.routes.send_email_verification_email", lambda user, url: sent.append(url))
    _expire(app, owner)
    client.get("/auth/logout")
    resp = client.post("/auth/confirmer-email/nouveau-lien", data={"email": owner.email}, follow_redirects=True)
    assert "nouveau lien de confirmation vient d" in resp.get_data(as_text=True)
    assert len(sent) == 1

    # toujours bloque tant que le lien n'est pas utilise
    assert "il est bloque" in _login_attempt(client, owner).get_data(as_text=True)

    client.get(sent[0].split("http://localhost")[-1], follow_redirects=True)
    verified_at, _ = _get(app, owner)
    assert verified_at is not None
    assert _login_attempt(client, owner).status_code == 200
    assert client.get("/dashboard").status_code == 200


def test_new_link_request_is_generic_and_rate_limited(app, client, owner, monkeypatch):
    sent = []
    monkeypatch.setattr("app.blueprints.auth.routes.send_email_verification_email", lambda user, url: sent.append(url))
    _expire(app, owner)
    unknown = client.post("/auth/confirmer-email/nouveau-lien", data={"email": "inconnu@example.com"}, follow_redirects=True)
    known = client.post("/auth/confirmer-email/nouveau-lien", data={"email": owner.email}, follow_redirects=True)
    msg = "nouveau lien de confirmation vient d"
    assert msg in unknown.get_data(as_text=True) and msg in known.get_data(as_text=True)
    assert len(sent) == 1  # rien envoye pour l'adresse inconnue
    client.post("/auth/confirmer-email/nouveau-lien", data={"email": owner.email}, follow_redirects=True)
    assert len(sent) == 1  # deuxieme demande immediate ignoree (delai de 2 minutes)


def test_expired_confirmation_link_does_not_unblock(app, client, owner):
    _expire(app, owner)
    with app.test_request_context():
        with tenant_bypass():
            from app.blueprints.auth.routes import _create_verification_token

            raw = _create_verification_token(db.session.get(User, owner.id))
            db.session.commit()
            token = EmailVerificationToken.query.filter_by(user_id=owner.id).first()
            token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.session.commit()
    client.get(f"/auth/confirmer-email/{raw}", follow_redirects=True)
    assert _get(app, owner)[0] is None
    assert "il est bloque" in _login_attempt(client, owner).get_data(as_text=True)


def test_password_reset_proves_the_mailbox(app, client, owner):
    from app.models.core import PasswordResetToken

    _expire(app, owner)
    with app.test_request_context():
        with tenant_bypass():
            raw = PasswordResetToken.generate_raw_token()
            db.session.add(PasswordResetToken(
                tenant_id=owner.tenant_id, user_id=owner.id, token_hash=PasswordResetToken.hash_token(raw),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ))
            db.session.commit()
    client.get("/auth/logout")
    client.post(f"/auth/reinitialiser-mot-de-passe/{raw}",
                data={"password": "NouveauPass1234!", "password_confirm": "NouveauPass1234!"}, follow_redirects=True)
    assert _get(app, owner)[0] is not None


# --------------------------------------------------- qui n'est PAS concerne

def test_only_self_signup_owners_are_concerned(app, client, tenant, owner, manager, worker):
    # manager et worker : crees par le proprietaire, sans echeance, jamais bloques
    for user in (manager, worker):
        _set(app, user, email_verified_at=None, email_confirm_deadline=None)
        assert "il est bloque" not in _login_attempt(client, user).get_data(as_text=True)
        assert client.get("/dashboard").status_code == 200
    # proprietaire sans echeance (cree par un administrateur, ou deja en base) : pas bloque
    _set(app, owner, email_verified_at=None, email_confirm_deadline=None)
    assert client.get("/auth/logout") and _login_attempt(client, owner).status_code == 200
    assert client.get("/dashboard").status_code == 200


def test_confirmed_owner_is_never_blocked(app, client, owner):
    _set(app, owner, email_verified_at=datetime.now(timezone.utc),
         email_confirm_deadline=datetime.now(timezone.utc) - timedelta(days=5))
    _login_attempt(client, owner)
    assert client.get("/dashboard").status_code == 200
