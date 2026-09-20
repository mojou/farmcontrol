"""Catalogue des formules tarifaires (paragraphe module paiement).

Tarifs volontairement accessibles pour le marche camerounais / CEMAC (FCFA).
"""
from datetime import timedelta

from flask_babel import lazy_gettext as _l

from app.extensions import db
from app.models import utcnow
from app.models.billing import SUBSCRIPTION_STATUS_TRIALING, Plan, Subscription

# A l'inscription libre, chaque nouvelle exploitation beneficie d'un essai
# gratuit du plan Pro pendant TRIAL_DAYS jours (pour decouvrir toutes les
# fonctionnalites) avant de retomber automatiquement sur le plan gratuit
# Decouverte si aucun paiement n'est effectue (voir get_current_plan : des
# que current_period_end est depasse, is_valid devient faux).
TRIAL_PLAN_CODE = "pro"
TRIAL_DAYS = 14

DEFAULT_PLANS = [
    {
        "code": "decouverte",
        "name": "Decouverte",
        "price_xaf": 0,
        "max_farms": 1,
        "max_active_batches": 1,
        "max_users": 1,
        "max_messages_per_day": 2,
        "description": "Pour demarrer : 1 ferme, 1 lot actif, 1 utilisateur (le proprietaire).",
        "sort_order": 1,
    },
    {
        "code": "standard",
        "name": "Standard",
        "price_xaf": 5000,
        "max_farms": 3,
        "max_active_batches": None,
        "max_users": 10,
        "max_messages_per_day": None,
        "description": "Jusqu'a 3 fermes, lots illimites, messagerie illimitee, alertes email, export PDF.",
        "sort_order": 2,
    },
    {
        "code": "pro",
        "name": "Pro",
        "price_xaf": 15000,
        "max_farms": None,
        "max_active_batches": None,
        "max_users": None,
        "max_messages_per_day": None,
        "description": "Fermes, lots, utilisateurs et messagerie illimites, support prioritaire.",
        "sort_order": 3,
    },
]


# Les plans sont stockes en base (texte francais) : ces marqueurs servent
# uniquement a l'extraction des traductions (les gabarits affichent
# _(plan.name) / _(plan.description)).
_PLAN_TEXT_MARKERS = (
    _l("Decouverte"),
    _l("Pour demarrer : 1 ferme, 1 lot actif, 1 utilisateur (le proprietaire)."),
    _l("Jusqu'a 3 fermes, lots illimites, messagerie illimitee, alertes email, export PDF."),
    _l("Fermes, lots, utilisateurs et messagerie illimites, support prioritaire."),
)


def ensure_plans_seeded():
    """Cree le catalogue de plans par defaut s'il n'existe pas encore.

    Idempotent : peut etre appele a chaque requete sans effet de bord une
    fois les plans crees (simple verification de presence).
    """
    if Plan.query.first() is not None:
        return

    for data in DEFAULT_PLANS:
        db.session.add(Plan(is_active=True, **data))
    db.session.commit()


def get_free_plan():
    ensure_plans_seeded()
    return Plan.query.filter_by(code="decouverte").first()


def get_current_plan(tenant):
    """Plan actif d'un tenant, ou le plan gratuit par defaut si aucun
    abonnement n'existe encore (compte cree avant l'ajout de ce module)."""
    if tenant and tenant.subscription and tenant.subscription.is_valid:
        return tenant.subscription.plan
    return get_free_plan()


def start_trial_subscription(tenant):
    """Demarre l'essai gratuit du plan Pro pour un tenant qui vient de
    s'inscrire (inscription libre). Ne fait rien pour les tenants crees par
    le super administrateur (voir core.tenant_new, qui gere son propre choix
    de plan explicite)."""
    ensure_plans_seeded()
    trial_plan = Plan.query.filter_by(code=TRIAL_PLAN_CODE).first() or get_free_plan()
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=trial_plan.id,
        status=SUBSCRIPTION_STATUS_TRIALING,
        current_period_start=utcnow(),
        current_period_end=utcnow() + timedelta(days=TRIAL_DAYS),
    )
    db.session.add(subscription)
    tenant.plan = trial_plan.code
    return subscription
