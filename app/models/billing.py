"""Module d'abonnement et de paiement (multitenant, tarifs en FCFA/XAF).

Plan : catalogue des formules disponibles (independant du tenant).
Subscription : abonnement courant d'un tenant a un plan.
PaymentTransaction : historique des tentatives de paiement (CinetPay).

Ce module reste volontairement simple (pas de facturation proratisee, pas
de gestion de TVA) : un abonnement est actif jusqu'a sa date d'expiration,
renouvelable manuellement par un nouveau paiement.
"""
from app.extensions import db
from app.models import TenantMixin, TimestampMixin

SUBSCRIPTION_STATUS_TRIALING = "trialing"
SUBSCRIPTION_STATUS_ACTIVE = "active"
SUBSCRIPTION_STATUS_EXPIRED = "expired"
SUBSCRIPTION_STATUS_CANCELED = "canceled"
SUBSCRIPTION_STATUSES = [
    SUBSCRIPTION_STATUS_TRIALING,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_EXPIRED,
    SUBSCRIPTION_STATUS_CANCELED,
]

PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_COMPLETED = "completed"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUSES = [PAYMENT_STATUS_PENDING, PAYMENT_STATUS_COMPLETED, PAYMENT_STATUS_FAILED]


class Plan(TimestampMixin, db.Model):
    """Formule tarifaire. Catalogue commun a tous les tenants (non scope)."""

    __tablename__ = "billing_plans"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    price_xaf = db.Column(db.Integer, nullable=False, default=0)  # FCFA, par mois, 0 = gratuit
    billing_period_days = db.Column(db.Integer, nullable=False, default=30)
    max_farms = db.Column(db.Integer, nullable=True)  # None = illimite
    max_active_batches = db.Column(db.Integer, nullable=True)  # None = illimite
    max_users = db.Column(db.Integer, nullable=True)  # None = illimite
    max_messages_per_day = db.Column(db.Integer, nullable=True)  # None = illimite
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<Plan {self.code}>"


class Subscription(TimestampMixin, TenantMixin, db.Model):
    """Abonnement courant d'un tenant (un seul actif a la fois)."""

    __tablename__ = "billing_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("billing_plans.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=SUBSCRIPTION_STATUS_TRIALING)
    current_period_start = db.Column(db.DateTime(timezone=True), nullable=True)
    current_period_end = db.Column(db.DateTime(timezone=True), nullable=True)  # None = jamais expire (plan gratuit)

    plan = db.relationship("Plan")

    @property
    def is_valid(self) -> bool:
        from app.models import utcnow

        if self.status not in (SUBSCRIPTION_STATUS_TRIALING, SUBSCRIPTION_STATUS_ACTIVE):
            return False
        if self.current_period_end is None:
            return True
        return self.current_period_end >= utcnow()


class PaymentTransaction(TimestampMixin, TenantMixin, db.Model):
    """Historique des tentatives de paiement (paragraphe module paiement)."""

    __tablename__ = "billing_payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("billing_plans.id"), nullable=False)

    provider = db.Column(db.String(30), nullable=False, default="cinetpay")
    provider_transaction_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    amount_xaf = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=PAYMENT_STATUS_PENDING)
    payment_method = db.Column(db.String(30), nullable=True)  # ex: MOBILE_MONEY, CREDIT_CARD
    raw_response = db.Column(db.JSON, nullable=True)

    plan = db.relationship("Plan")

    def __repr__(self):
        return f"<PaymentTransaction {self.provider_transaction_id} {self.status}>"
