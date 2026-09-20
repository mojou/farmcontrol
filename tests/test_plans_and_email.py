"""Plan gratuit limite a 1 utilisateur ; lien de confirmation d'email valable
3 heures."""
from datetime import datetime, timedelta, timezone

from flask import render_template

from app.extensions import db
from app.models.core import EmailVerificationToken, User
from app.utils.plans import DEFAULT_PLANS, get_free_plan, start_trial_subscription
from app.utils.tenant import tenant_bypass
from tests.conftest import TEST_PASSWORD, login


def _user_form(**over):
    data = {
        "first_name": "Nouveau", "last_name": "Employe", "email": "employe-test@example.com",
        "role": "worker", "farm_id": "0", "password": TEST_PASSWORD, "confirm_password": TEST_PASSWORD,
    }
    data.update(over)
    return data


def _count_users(app, tenant):
    with app.app_context():
        with tenant_bypass():
            return User.query.filter_by(tenant_id=tenant.id).count()


# ------------------------------------------------------------------ plan gratuit

def test_free_plan_definition_is_one_user():
    free = next(p for p in DEFAULT_PLANS if p["code"] == "decouverte")
    assert free["max_users"] == 1
    assert "1 utilisateur" in free["description"] and "3 utilisateurs" not in free["description"]


def test_free_plan_in_database_is_one_user(app):
    with app.app_context():
        with tenant_bypass():
            assert get_free_plan().max_users == 1


def test_owner_on_free_plan_cannot_add_a_user(app, client, tenant, owner):
    login(client, owner)
    resp = client.post("/users/new", data=_user_form(), follow_redirects=True)
    assert resp.status_code == 200
    assert _count_users(app, tenant) == 1  # seulement le proprietaire
    assert "limite a 1 utilisateur" in resp.get_data(as_text=True)

    client.get("/langue/en")
    html = client.post("/users/new", data=_user_form(), follow_redirects=True).get_data(as_text=True)
    assert "limited to 1 user" in html


def test_pro_trial_allows_more_users(app, client, tenant, owner):
    with app.app_context():
        with tenant_bypass():
            db.session.merge(tenant)
            start_trial_subscription(db.session.get(type(tenant), tenant.id))
            db.session.commit()
    login(client, owner)
    client.post("/users/new", data=_user_form(), follow_redirects=True)
    assert _count_users(app, tenant) == 2


def test_pricing_page_shows_one_user_for_free_plan(client):
    html = client.get("/tarifs").get_data(as_text=True)
    assert "1 utilisateur(s) maximum" in html
    client.get("/langue/en")
    html = client.get("/tarifs").get_data(as_text=True)
    assert "1 user(s) maximum" in html


# ------------------------------------------------------- email de confirmation

def test_verification_link_lasts_three_hours(app, tenant, owner):
    assert app.config["EMAIL_VERIFICATION_TOKEN_HOURS"] == 3
    from app.blueprints.auth.routes import _create_verification_token

    with app.test_request_context():
        with tenant_bypass():
            user = db.session.get(User, owner.id)
            before = datetime.now(timezone.utc)
            _create_verification_token(user)
            db.session.commit()
            token = EmailVerificationToken.query.filter_by(user_id=owner.id).first()
            delta = token.expires_at - before
            assert timedelta(hours=2, minutes=59) <= delta <= timedelta(hours=3, minutes=1)


def test_expired_verification_link_is_refused(app, client, tenant, owner):
    from app.blueprints.auth.routes import _create_verification_token

    with app.test_request_context():
        with tenant_bypass():
            user = db.session.get(User, owner.id)
            raw = _create_verification_token(user)
            db.session.commit()
            token = EmailVerificationToken.query.filter_by(user_id=owner.id).first()
            token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # 3 h + 1 min plus tard
            db.session.commit()
    resp = client.get(f"/auth/confirmer-email/{raw}", follow_redirects=True)
    assert "invalide ou a expire" in resp.get_data(as_text=True)
    with app.app_context():
        with tenant_bypass():
            assert db.session.get(User, owner.id).email_verified_at is None


def test_valid_verification_link_confirms_the_email(app, client, tenant, owner):
    from app.blueprints.auth.routes import _create_verification_token

    with app.test_request_context():
        with tenant_bypass():
            raw = _create_verification_token(db.session.get(User, owner.id))
            db.session.commit()
    client.get(f"/auth/confirmer-email/{raw}", follow_redirects=True)
    with app.app_context():
        with tenant_bypass():
            assert db.session.get(User, owner.id).email_verified_at is not None


def test_confirmation_emails_state_the_validity(app, owner):
    with app.test_request_context():
        for template in ("email/verify_email.html", "email/verify_email.txt"):
            body = render_template(template, user=owner, verify_url="https://exemple.test/x")
            assert "valable 3 heures" in body, template
        body = render_template("email/welcome.txt", user=owner, temporary_password=None, verify_url="https://exemple.test/x")
        assert "valable 3 heures" in body
