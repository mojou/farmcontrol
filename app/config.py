"""Configuration de l'application Farm Control.

Toutes les valeurs sensibles sont lues depuis les variables d'environnement
(.env en developpement). Aucune valeur secrete ne doit etre codee en dur ici.
"""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://farmcontrol:farmcontrol@localhost:5432/farmcontrol",
    )

    # Bilingue francais/anglais (Cameroun) - voir app._select_locale.
    BABEL_DEFAULT_LOCALE = "fr"
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(BASE_DIR, "app", "translations")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    ENFORCE_RLS = _bool_env("ENFORCE_RLS", True)

    # Emails
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 25))
    MAIL_USE_TLS = _bool_env("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _bool_env("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "notifications@farmcontrol.app")
    MAIL_SUPPRESS_SEND = _bool_env("MAIL_SUPPRESS_SEND", False)

    # Envoi transactionnel via l'API HTTP Brevo (voir app/utils/brevo.py) :
    # prend le pas sur le SMTP classique des que BREVO_API_KEY est renseigne.
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")

    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, os.environ.get("UPLOAD_FOLDER", "uploads"))
    MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", 2))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_SIZE_MB", 2)) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

    # Paiement (CinetPay - Mobile Money / carte, tarifs en FCFA/XAF)
    # Conserve mais inactif : voir SASPAY ci-dessous, le fournisseur utilise
    # actuellement. CINETPAY_ENABLED redeviendra vrai le jour ou ses
    # identifiants sont a nouveau renseignes.
    CINETPAY_API_KEY = os.environ.get("CINETPAY_API_KEY")
    CINETPAY_SITE_ID = os.environ.get("CINETPAY_SITE_ID")
    CINETPAY_BASE_URL = os.environ.get("CINETPAY_BASE_URL", "https://api-checkout.cinetpay.com/v2")
    CINETPAY_CURRENCY = "XAF"
    CINETPAY_ENABLED = bool(CINETPAY_API_KEY and CINETPAY_SITE_ID)

    # Paiement (SasPay - agregateur mobile money/carte, Afrique de l'Ouest et
    # Centrale). Documentation : https://docs.saspay.me
    SASPAY_SECRET_KEY = os.environ.get("SASPAY_SECRET_KEY")
    SASPAY_BASE_URL = os.environ.get("SASPAY_BASE_URL", "https://api.saspay.me/api/v1")
    SASPAY_CURRENCY = "XAF"
    SASPAY_COUNTRY = "CM"
    # Secret de signature des webhooks (distinct de la clef API), affiche une
    # seule fois a la creation du webhook dans le tableau de bord SasPay.
    SASPAY_WEBHOOK_SECRET = os.environ.get("SASPAY_WEBHOOK_SECRET")
    # Actif seulement si la clef secrete est renseignee. Sinon l'abonnement
    # passe en mode demonstration (paiement simule, clairement annonce a
    # l'ecran) pour ne jamais bloquer la demonstration du produit.
    SASPAY_ENABLED = bool(SASPAY_SECRET_KEY)

    # Securite authentification
    PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", 10))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", 5))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", 15))
    PASSWORD_RESET_TOKEN_MINUTES = int(os.environ.get("PASSWORD_RESET_TOKEN_MINUTES", 30))
    EMAIL_VERIFICATION_TOKEN_HOURS = int(os.environ.get("EMAIL_VERIFICATION_TOKEN_HOURS", 48))

    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Mode demo
    DEMO_TENANT_SLUG = os.environ.get("DEMO_TENANT_SLUG", "demo")
    DEMO_RESET_ENABLED = _bool_env("DEMO_RESET_ENABLED", True)

    WTF_CSRF_TIME_LIMIT = None


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://farmcontrol:farmcontrol@localhost:5432/farmcontrol_test",
    )
    ENFORCE_RLS = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
