"""Catalogue des formules tarifaires (paragraphe module paiement).

Tarifs volontairement accessibles pour le marche camerounais / CEMAC (FCFA).
"""
from app.extensions import db
from app.models.billing import Plan

DEFAULT_PLANS = [
    {
        "code": "decouverte",
        "name": "Decouverte",
        "price_xaf": 0,
        "max_farms": 1,
        "max_active_batches": 1,
        "max_users": 3,
        "max_messages_per_day": 2,
        "description": "Pour demarrer : 1 ferme, 1 lot actif, jusqu'a 3 utilisateurs, 2 messages/jour.",
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
