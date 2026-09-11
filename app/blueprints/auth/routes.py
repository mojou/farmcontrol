from datetime import datetime, timedelta, timezone

from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    ResetPasswordForm,
)
from app.extensions import db
from app.models.core import PasswordResetToken, User
from app.utils.audit import log_action
from app.utils.emailing import send_password_reset_email
from app.utils.security import validate_password_policy
from app.utils.tenant import tenant_bypass


def _redirect_after_login():
    if current_user.is_super_admin():
        return redirect(url_for("core.admin_dashboard"))
    return redirect(url_for("core.dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_after_login()

    form = LoginForm()
    if form.validate_on_submit():
        with tenant_bypass():
            user = User.query.filter_by(email=form.email.data.strip().lower()).first()

        if user is None or not user.is_active:
            flash("Identifiants incorrects.", "danger")
            return render_template("auth/login.html", form=form)

        if user.is_locked():
            minutes = max(int((user.locked_until - datetime.now(timezone.utc)).total_seconds() // 60) + 1, 1)
            flash(f"Compte temporairement verrouille. Reessayez dans {minutes} minute(s).", "danger")
            return render_template("auth/login.html", form=form)

        if not user.check_password(form.password.data):
            user.register_failed_login(
                current_app.config["MAX_LOGIN_ATTEMPTS"], current_app.config["LOGIN_LOCKOUT_MINUTES"]
            )
            db.session.commit()
            flash("Identifiants incorrects.", "danger")
            return render_template("auth/login.html", form=form)

        if user.tenant and not user.tenant.is_active:
            flash("Ce compte est desactive. Contactez votre administrateur.", "danger")
            return render_template("auth/login.html", form=form)

        user.register_successful_login()
        db.session.commit()
        login_user(user, remember=form.remember_me.data)
        flash(f"Bienvenue, {user.first_name}.", "success")
        return _redirect_after_login()

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez ete deconnecte.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return _redirect_after_login()

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        with tenant_bypass():
            user = User.query.filter_by(email=form.email.data.strip().lower()).first()

        if user:
            raw_token = PasswordResetToken.generate_raw_token()
            reset_token = PasswordResetToken(
                tenant_id=user.tenant_id,
                user_id=user.id,
                token_hash=PasswordResetToken.hash_token(raw_token),
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=current_app.config["PASSWORD_RESET_TOKEN_MINUTES"]),
            )
            db.session.add(reset_token)
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=raw_token, _external=True)
            try:
                send_password_reset_email(user, reset_url)
            except Exception:
                current_app.logger.exception("Echec de l'envoi de l'email de reinitialisation")

        # Message identique que l'email existe ou non (evite l'enumeration de comptes).
        flash("Si un compte existe avec cet email, un lien de reinitialisation a ete envoye.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reinitialiser-mot-de-passe/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return _redirect_after_login()

    with tenant_bypass():
        candidates = PasswordResetToken.query.filter(
            PasswordResetToken.used_at.is_(None)
        ).all()
    matching_token = next((t for t in candidates if t.check_token(token) and t.is_valid()), None)

    if matching_token is None:
        flash("Ce lien de reinitialisation est invalide ou a expire.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        errors = validate_password_policy(form.password.data)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth/reset_password.html", form=form)

        with tenant_bypass():
            user = db.session.get(User, matching_token.user_id)
        user.set_password(form.password.data)
        matching_token.used_at = datetime.now(timezone.utc)
        log_action("update", "users", user.id, {"action": "password_reset"})
        db.session.commit()
        flash("Votre mot de passe a ete reinitialise. Vous pouvez vous connecter.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)


@auth_bp.route("/mon-compte/mot-de-passe", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Mot de passe actuel incorrect.", "danger")
            return render_template("auth/change_password.html", form=form)

        errors = validate_password_policy(form.password.data)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.password.data)
        log_action("update", "users", current_user.id, {"action": "password_change"})
        db.session.commit()
        flash("Mot de passe mis a jour avec succes.", "success")
        return redirect(url_for("core.profile"))

    return render_template("auth/change_password.html", form=form)
