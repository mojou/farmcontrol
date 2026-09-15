from datetime import datetime, timedelta, timezone

from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    ResetPasswordForm,
    SignupForm,
)
from app.extensions import db
from app.models.core import EmailVerificationToken, ROLE_OWNER, PasswordResetToken, Tenant, User
from app.utils.audit import log_action
from app.utils.emailing import send_email_verification_email, send_password_reset_email, send_welcome_email
from app.utils.plans import TRIAL_DAYS, start_trial_subscription
from app.utils.security import generate_unique_slug, validate_password_policy
from app.utils.tenant import tenant_bypass


def _redirect_after_login():
    if current_user.is_super_admin():
        return redirect(url_for("core.admin_dashboard"))
    return redirect(url_for("core.dashboard"))


def _create_verification_token(user) -> str:
    """Cree un jeton de confirmation d'email (ajoute a la session sans
    commit : a l'appelant de committer, pour rester dans la meme
    transaction/contexte RLS que la creation de l'utilisateur)."""
    raw_token = EmailVerificationToken.generate_raw_token()
    token = EmailVerificationToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=EmailVerificationToken.hash_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=current_app.config["EMAIL_VERIFICATION_TOKEN_HOURS"]),
    )
    db.session.add(token)
    return raw_token


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_after_login()

    form = LoginForm()
    if form.validate_on_submit():
        # Le tenant de l'utilisateur n'est pas encore connu avant de l'avoir
        # trouve : toute la sequence recherche + mises a jour (compteur
        # d'echecs, verrouillage, derniere connexion) reste donc dans un seul
        # contexte de bypass RLS, jusqu'au commit final inclus.
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


@auth_bp.route("/inscription", methods=["GET", "POST"])
def signup():
    """Creation libre d'un compte (chacun cree sa propre exploitation), a la
    maniere d'un produit SaaS grand public (ex. Odoo) : cree un nouveau
    tenant et son premier utilisateur, avec le role proprietaire.
    """
    if current_user.is_authenticated:
        return _redirect_after_login()

    form = SignupForm()
    if form.validate_on_submit():
        errors = validate_password_policy(form.password.data)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth/signup.html", form=form)

        email = form.email.data.strip().lower()
        with tenant_bypass():
            email_taken = User.query.filter_by(email=email).first()
            if email_taken:
                flash("Un compte existe deja avec cet email. Connectez-vous.", "danger")
                return render_template("auth/signup.html", form=form)

            slug = generate_unique_slug(
                form.organization_name.data,
                lambda candidate: Tenant.query.filter_by(slug=candidate).first() is not None,
            )

            tenant = Tenant(name=form.organization_name.data.strip(), slug=slug)
            db.session.add(tenant)
            db.session.flush()

            owner = User(
                tenant_id=tenant.id,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=email,
                role=ROLE_OWNER,
            )
            owner.set_password(form.password.data)
            db.session.add(owner)
            db.session.flush()

            start_trial_subscription(tenant)
            raw_verify_token = _create_verification_token(owner)

            log_action("create", "tenants", tenant.id, {"name": tenant.name, "slug": tenant.slug, "via": "signup"})
            db.session.commit()

        try:
            verify_url = url_for("auth.verify_email", token=raw_verify_token, _external=True)
            send_welcome_email(owner, verify_url=verify_url)
        except Exception:
            current_app.logger.exception("Echec de l'envoi de l'email de bienvenue")

        login_user(owner)
        flash(
            f"Bienvenue sur Farm Control, {owner.first_name}. Votre espace est pret, avec "
            f"{TRIAL_DAYS} jours d'essai gratuit du plan Pro (toutes les fonctionnalites debloquees).",
            "success",
        )
        return _redirect_after_login()

    return render_template("auth/signup.html", form=form)


@auth_bp.route("/confirmer-email/<token>")
def verify_email(token):
    with tenant_bypass():
        candidates = EmailVerificationToken.query.filter(EmailVerificationToken.used_at.is_(None)).all()
        matching_token = next((t for t in candidates if t.check_token(token) and t.is_valid()), None)

        if matching_token is None:
            flash("Ce lien de confirmation est invalide ou a expire.", "danger")
            return redirect(url_for("auth.login"))

        user = db.session.get(User, matching_token.user_id)
        user.email_verified_at = datetime.now(timezone.utc)
        matching_token.used_at = datetime.now(timezone.utc)
        log_action("update", "users", user.id, {"action": "email_verified"})
        db.session.commit()

    flash("Votre adresse email est confirmee. Merci !", "success")
    if current_user.is_authenticated:
        return _redirect_after_login()
    return redirect(url_for("auth.login"))


@auth_bp.route("/confirmer-email/renvoyer", methods=["POST"])
@login_required
def resend_verification_email():
    if current_user.is_email_verified:
        flash("Votre email est deja confirme.", "info")
        return redirect(url_for("core.dashboard"))

    raw_token = _create_verification_token(current_user)
    db.session.commit()

    try:
        verify_url = url_for("auth.verify_email", token=raw_token, _external=True)
        send_email_verification_email(current_user, verify_url)
        flash("Email de confirmation renvoye. Verifiez votre boite de reception.", "success")
    except Exception:
        current_app.logger.exception("Echec du renvoi de l'email de confirmation")
        flash("Impossible d'envoyer l'email pour le moment. Reessayez plus tard.", "danger")

    return redirect(url_for("core.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez ete deconnecte.", "info")
    return redirect(url_for("core.index"))


@auth_bp.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return _redirect_after_login()

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        # Recherche + creation du jeton dans le meme contexte de bypass RLS :
        # le tenant de l'utilisateur n'est pas connu avant de l'avoir trouve,
        # et la requete est anonyme (pas de tenant_id de session a utiliser).
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

        if user:
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
