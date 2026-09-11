"""Modeles du coeur de la plateforme (Core) : tenants, utilisateurs, audit.

Ces modeles sont independants du metier "elevage" et seront reutilises par
les futurs modules (porcs, pisciculture, etc.).
"""
import secrets
from datetime import timedelta

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import TenantMixin, TimestampMixin, utcnow

ROLE_SUPER_ADMIN = "super_admin"
ROLE_OWNER = "owner"
ROLE_MANAGER = "manager"
ROLE_WORKER = "worker"

ROLES = [ROLE_SUPER_ADMIN, ROLE_OWNER, ROLE_MANAGER, ROLE_WORKER]

ROLE_LABELS = {
    ROLE_SUPER_ADMIN: "Super administrateur",
    ROLE_OWNER: "Proprietaire",
    ROLE_MANAGER: "Responsable",
    ROLE_WORKER: "Travailleur",
}


class Tenant(TimestampMixin, db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    plan = db.Column(db.String(40), nullable=False, default="standard")

    users = db.relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    farms = db.relationship("Farm", back_populates="tenant", cascade="all, delete-orphan")

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
