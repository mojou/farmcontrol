"""Modeles du coeur de la plateforme (Core) : tenants, utilisateurs, audit.

Ces modeles sont independants du metier "elevage" et seront reutilises par
les futurs modules (porcs, pisciculture, etc.).
"""
import secrets
from datetime import timedelta

from flask_babel import lazy_gettext as _l
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import TenantMixin, TimestampMixin, utcnow

ROLE_SUPER_ADMIN = "super_admin"
ROLE_OWNER = "owner"
ROLE_MANAGER = "manager"
ROLE_WORKER = "worker"

ROLES = [ROLE_SUPER_ADMIN, ROLE_OWNER, ROLE_MANAGER, ROLE_WORKER]

# lazy_gettext (pas gettext) : ce dictionnaire est construit une seule fois
# a l'import du module, avant qu'aucune requete/langue ne soit connue - la
# traduction doit donc etre differee jusqu'au rendu reel (paragraphe bilingue).
ROLE_LABELS = {
    ROLE_SUPER_ADMIN: _l("Super administrateur"),
    ROLE_OWNER: _l("Proprietaire"),
    ROLE_MANAGER: _l("Responsable"),
    ROLE_WORKER: _l("Travailleur"),
}


class Tenant(TimestampMixin, db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    plan = db.Column(db.String(40), nullable=False, default="standard")

    # Parametres generaux (page /parametres) : pays et langue par defaut
    # appliques aux nouveaux utilisateurs crees par le proprietaire, et
    # libelle de devise utilise par le filtre `currency` cote affichage
    # uniquement (la devise de facturation CinetPay reste XAF, voir
    # app.utils.cinetpay - ce champ ne change pas les montants factures).
    country = db.Column(db.String(80), nullable=True)
    default_language = db.Column(db.String(5), nullable=False, default="fr")
    currency_label = db.Column(db.String(10), nullable=False, default="FCFA")

    # -- Elevage : valeurs par defaut suggerees a la creation d'un lot -----
    default_breed = db.Column(db.String(100), nullable=True)
    default_cycle_days = db.Column(db.Integer, nullable=True)
    fcr_alert_threshold = db.Column(db.Numeric(4, 2), nullable=True)

    # -- Alertes -------------------------------------------------------
    mortality_alert_threshold_percent = db.Column(db.Numeric(5, 2), nullable=False, default=3)
    sanitary_reminder_interval_minutes = db.Column(db.Integer, nullable=False, default=10)
    email_alerts_enabled = db.Column(db.Boolean, nullable=False, default=True)

    # -- Types d'elevage (voir app/utils/species.py) ----------------------
    # Type principal (propose par defaut a la creation d'un lot) et liste
    # des types pratiques, separes par des virgules.
    primary_species = db.Column(db.String(30), nullable=False, default="broiler", server_default="broiler")
    enabled_species = db.Column(db.String(255), nullable=False, default="broiler", server_default="broiler")

    # -- Stock -----------------------------------------------------------
    default_stock_low_threshold = db.Column(db.Numeric(10, 2), nullable=True)

    # -- Finance -----------------------------------------------------------
    default_labor_cost_per_day = db.Column(db.Numeric(10, 2), nullable=True)
    default_sale_unit = db.Column(db.String(10), nullable=False, default="unit")

    # -- Securite (remplace les valeurs par defaut globales de app.config
    # pour ce tenant - voir auth.login) --------------------------------
    max_login_attempts = db.Column(db.Integer, nullable=False, default=5)
    login_lockout_minutes = db.Column(db.Integer, nullable=False, default=15)

    users = db.relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    farms = db.relationship("Farm", back_populates="tenant", cascade="all, delete-orphan")
    subscription = db.relationship(
        "Subscription", uselist=False, cascade="all, delete-orphan", backref="tenant"
    )
    payment_transactions = db.relationship(
        "PaymentTransaction", cascade="all, delete-orphan", backref="tenant"
    )
    sanitary_program_templates = db.relationship(
        "SanitaryProgramTemplateItem", cascade="all, delete-orphan"
    )
    suppliers = db.relationship("Supplier", cascade="all, delete-orphan")
    growth_references = db.relationship("GrowthReference", cascade="all, delete-orphan")
    # Une alerte n'est pas toujours rattachee a une ferme/un lot (farm_id et
    # batch_id sont nullable) : sans ce lien direct depuis Tenant, ces
    # alertes "orphelines" n'etaient couvertes par aucune cascade et
    # bloquaient la suppression du tenant (meme bug deja rencontre pour
    # SanitaryProgramTemplateItem et Supplier ci-dessus).
    alerts = db.relationship("Alert", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant {self.slug}>"


class User(TimestampMixin, TenantMixin, UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    farm_id = db.Column(db.Integer, db.ForeignKey("farms.id"), nullable=True, index=True)

    email = db.Column(db.String(255), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_WORKER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    email_notifications_enabled = db.Column(db.Boolean, nullable=False, default=True)
    avatar_path = db.Column(db.String(255), nullable=True)
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Inscription libre : le compte proprietaire est bloque si l'email n'est
    # pas confirme avant cette date (EMAIL_VERIFICATION_TOKEN_HOURS apres
    # l'inscription). NULL = pas d'echeance (comptes crees par un
    # administrateur ou un proprietaire, comptes deja confirmes).
    email_confirm_deadline = db.Column(db.DateTime(timezone=True), nullable=True)
    preferred_language = db.Column(db.String(5), nullable=False, default="fr")

    failed_login_count = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    tenant = db.relationship("Tenant", back_populates="users")
    farm = db.relationship("Farm", back_populates="workers", foreign_keys=[farm_id])
    # Sans cascade explicite : a la suppression d'un utilisateur, ses entrees
    # d'audit sont conservees (traçabilite, paragraphe 7.3) et simplement
    # detachees (user_id mis a NULL, colonne nullable) plutot que supprimees.
    audit_logs = db.relationship("AuditLog", back_populates="user")
    password_reset_tokens = db.relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens = db.relationship(
        "EmailVerificationToken", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    # -- Mot de passe -----------------------------------------------------
    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # -- Verrouillage apres echecs de connexion ---------------------------
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > utcnow())

    def register_failed_login(self, max_attempts: int, lockout_minutes: int):
        self.failed_login_count += 1
        if self.failed_login_count >= max_attempts:
            self.locked_until = utcnow() + timedelta(minutes=lockout_minutes)

    def register_successful_login(self):
        self.failed_login_count = 0
        self.locked_until = None
        self.last_login_at = utcnow()

    # -- Roles --------------------------------------------------------
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    def is_super_admin(self) -> bool:
        return self.role == ROLE_SUPER_ADMIN

    def is_owner(self) -> bool:
        return self.role == ROLE_OWNER

    def is_manager(self) -> bool:
        return self.role == ROLE_MANAGER

    def is_worker(self) -> bool:
        return self.role == ROLE_WORKER

    def has_role(self, *roles) -> bool:
        return self.role in roles

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_blocked_unconfirmed(self) -> bool:
        """Compte proprietaire dont l'email n'a pas ete confirme dans le delai :
        il ne peut plus servir tant que le lien de confirmation n'a pas ete utilise."""
        return (
            self.email_verified_at is None
            and self.email_confirm_deadline is not None
            and utcnow() > self.email_confirm_deadline
        )

    @property
    def email_minutes_left(self):
        """Minutes restantes pour confirmer l'email avant blocage (None si pas d'echeance)."""
        if self.email_verified_at is not None or self.email_confirm_deadline is None:
            return None
        return max(int((self.email_confirm_deadline - utcnow()).total_seconds() // 60), 0)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class PasswordResetToken(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", back_populates="password_reset_tokens")

    @staticmethod
    def generate_raw_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return generate_password_hash(raw_token)

    def check_token(self, raw_token: str) -> bool:
        return check_password_hash(self.token_hash, raw_token)

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > utcnow()


class EmailVerificationToken(TimestampMixin, TenantMixin, db.Model):
    """Jeton envoye par email a la creation d'un compte pour confirmer que
    l'adresse email est valide et joignable (important puisque c'est aussi
    l'adresse utilisee pour la reinitialisation de mot de passe)."""

    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", back_populates="email_verification_tokens")

    @staticmethod
    def generate_raw_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return generate_password_hash(raw_token)

    def check_token(self, raw_token: str) -> bool:
        return check_password_hash(self.token_hash, raw_token)

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > utcnow()


class AuditLog(TenantMixin, db.Model):
    """Journal d'audit (paragraphe 7.3) : trace toute creation/modification/
    suppression sur les tables sensibles, avec le detail des champs modifies.
    """

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action = db.Column(db.String(20), nullable=False)  # create / update / delete
    table_name = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} {self.table_name}#{self.record_id}>"


class Message(TimestampMixin, TenantMixin, db.Model):
    """Messagerie interne entre utilisateurs d'un meme tenant (ex : entre un
    travailleur et le proprietaire/responsable de son exploitation).

    Volontairement simple pour la V1 : pas de fils de discussion structures,
    une reponse est un nouveau message dont le sujet est prefixe "Re:".
    """

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])

    def __repr__(self):
        return f"<Message {self.subject!r} -> user#{self.recipient_id}>"
