"""Fabrique de l'application Farm Control (application factory pattern)."""
import os

from flask import Flask, g, render_template, request, session
from flask_login import current_user

from app.config import config_by_name
from app.extensions import babel, csrf, db, login_manager, mail, migrate

SUPPORTED_LANGUAGES = ["fr", "en"]
DEFAULT_LANGUAGE = "fr"


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))

    _init_extensions(app)
    _register_blueprints(app)
    _register_request_hooks(app)
    _register_error_handlers(app)
    _register_template_helpers(app)

    from app.cli import register_cli

    register_cli(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app


def _select_locale():
    """Determine la langue de la requete courante (paragraphe accessibilite -
    Cameroun bilingue francais/anglais) : choix explicite en session en
    priorite (voir core.set_language), puis preference sauvegardee sur le
    profil utilisateur, puis langue du navigateur, puis francais par defaut.
    """
    if "lang" in session and session["lang"] in SUPPORTED_LANGUAGES:
        return session["lang"]
    if current_user.is_authenticated and getattr(current_user, "preferred_language", None) in SUPPORTED_LANGUAGES:
        return current_user.preferred_language
    return request.accept_languages.best_match(SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE)


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=_select_locale)

    from flask_babel import get_locale

    app.jinja_env.globals["get_locale"] = get_locale

    from app.models import register_tenant_filter

    register_tenant_filter(db)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.core import User
        from app.utils.tenant import tenant_bypass

        # Le chargement de l'utilisateur doit reussir avant meme que le
        # tenant courant ne soit connu (on le determine justement a partir
        # de l'utilisateur charge ici).
        with tenant_bypass():
            return db.session.get(User, int(user_id))


def _register_blueprints(app):
    from app.blueprints.auth import auth_bp
    from app.blueprints.billing import billing_bp
    from app.blueprints.core import core_bp
    from app.blueprints.messaging import messaging_bp
    from app.blueprints.poultry import poultry_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(poultry_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(messaging_bp)


def _register_request_hooks(app):
    from app.utils.rls import reset_rls_session, sync_rls_session
    from app.utils.tenant import set_current_tenant

    @app.before_request
    def load_tenant_context():
        g.tenant_bypass = False
        if current_user.is_authenticated:
            if current_user.is_super_admin():
                set_current_tenant(None)
                g.tenant_bypass = True
            else:
                set_current_tenant(current_user.tenant_id)
        else:
            set_current_tenant(None)

        sync_rls_session(is_super_admin=g.tenant_bypass)

    @app.teardown_request
    def clear_tenant_context(exc=None):
        try:
            reset_rls_session()
        except Exception:
            pass


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def _register_template_helpers(app):
    from app.models.core import ROLE_LABELS

    @app.template_filter("currency")
    def currency_filter(value):
        # FCFA (XAF) n'a pas de sous-unite en circulation : pas de decimales.
        # Le libelle affiche (Tenant.currency_label) est purement visuel :
        # la devise de facturation CinetPay reste XAF quel que soit ce
        # reglage (voir app.utils.cinetpay et core.settings).
        if value is None:
            return "-"
        label = "FCFA"
        if current_user.is_authenticated and current_user.tenant and current_user.tenant.currency_label:
            label = current_user.tenant.currency_label
        return f"{float(value):,.0f} {label}".replace(",", " ")

    @app.template_filter("weight")
    def weight_filter(grams, target=None):
        """Poids (stocke en grammes) dans l'unite du type d'elevage : "1 800 g"
        ou "85 kg". `target` : un lot, un type d'elevage ou "g"/"kg"."""
        if grams is None:
            return "-"
        from app.utils.species import get_species

        if target in ("g", "kg"):
            unit = target
        else:
            unit = get_species(getattr(target, "species", target)).profile.weight_unit
        if unit == "kg":
            return f"{float(grams) / 1000:,.1f} kg".replace(",", " ")
        return f"{float(grams):,.0f} g".replace(",", " ")

    @app.template_filter("number")
    def number_filter(value, decimals=0):
        if value is None:
            return "-"
        return f"{float(value):,.{decimals}f}".replace(",", " ")

    @app.context_processor
    def inject_globals():
        from flask import current_app

        unread_alerts_count = 0
        unread_messages_count = 0
        if current_user.is_authenticated and not current_user.is_super_admin():
            from app.models.core import Message
            from app.models.poultry import Alert

            unread_alerts_count = Alert.query.filter_by(is_read=False).count()
            unread_messages_count = Message.query.filter_by(
                recipient_id=current_user.id, is_read=False
            ).count()
        from app.utils.species import animal_term, animals_term, de_term, young_term

        tenant = current_user.tenant if current_user.is_authenticated and not current_user.is_super_admin() else None
        return {
            # Vocabulaire selon le type d'elevage : animals(lot) = "poulets",
            # "porcs"...; sans argument, celui de l'exploitation ("animaux" si
            # plusieurs types sont pratiques). Voir app/utils/species.py.
            "animals": lambda target=None: animals_term(target, tenant),
            "animal": lambda target=None: animal_term(target, tenant),
            "young": lambda target=None: young_term(target, tenant),
            "de": de_term,
            "role_labels": ROLE_LABELS,
            "current_user_obj": current_user,
            "unread_alerts_count": unread_alerts_count,
            "unread_messages_count": unread_messages_count,
            "cinetpay_enabled": current_app.config.get("CINETPAY_ENABLED"),
            "saspay_enabled": current_app.config.get("SASPAY_ENABLED"),
            "support_email": current_app.config.get("SUPPORT_EMAIL"),
        }
