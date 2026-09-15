"""Modeles SQLAlchemy et mecanisme d'isolation multitenant.

Isolation multitenant - couche applicative (paragraphe 7.1 du cahier des
charges) : tout modele heritant de TenantMixin est automatiquement filtre par
tenant_id sur SELECT/UPDATE/DELETE grace a un evenement SQLAlchemy
`do_orm_execute`. Ce filtrage est actif pour toute la duree de vie de
l'application des que `register_tenant_filter(db)` est appele (voir
app/__init__.py). La couche 2 (Row Level Security PostgreSQL) est mise en
place separement, voir scripts/enable_rls.sql et app/utils/rls.py.
"""
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.extensions import db
from app.utils.tenant import get_current_tenant_id, is_tenant_bypassed


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class TenantMixin:
    """A appliquer a tout modele appartenant a un tenant precis.

    La colonne `tenant_id` est declaree ici une seule fois : SQLAlchemy en
    copie une instance distincte (avec sa propre contrainte de cle etrangere)
    sur la table de chaque sous-classe. Un modele qui a besoin d'une regle
    differente (ex. `User.tenant_id` nullable pour les super administrateurs)
    peut simplement redeclarer la colonne dans son propre corps de classe :
    cette declaration explicite prend alors le pas sur celle du mixin.

    Le filtrage automatique par tenant (couche applicative, paragraphe 7.1)
    s'appuie directement sur cette colonne via `register_tenant_filter`.
    """

    __tenant_scoped__ = True

    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)


def register_tenant_filter(sa_db):
    """Enregistre le filtre global tenant_id sur toutes les requetes ORM.

    A appeler une seule fois, au demarrage de l'application.
    """

    @event.listens_for(Session, "do_orm_execute")
    def _add_tenant_filter(execute_state):
        if not execute_state.is_select:
            return
        if is_tenant_bypassed():
            return
        tenant_id = get_current_tenant_id()
        if tenant_id is None:
            # Aucun tenant actif dans le contexte courant : on ne renvoie
            # aucune ligne des modeles scoped plutot que de fuiter des
            # donnees d'un autre tenant par erreur.
            tenant_id = -1
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.tenant_id == tenant_id,
                include_aliases=True,
            )
        )


# Import des modeles pour qu'ils soient enregistres aupres de SQLAlchemy /
# Flask-Migrate (necessaire pour la detection automatique des migrations).
from app.models.core import Tenant, User, AuditLog, PasswordResetToken, Message  # noqa: E402,F401
from app.models.poultry import (  # noqa: E402,F401
    Farm,
    Batch,
    BatchDay,
    StockItem,
    FeedRecord,
    WaterRecord,
    MortalityRecord,
    WoodRecord,
    MedicationRecord,
    Observation,
    WeightRecord,
    BatchFinance,
    Alert,
    SanitaryProgramItem,
    SanitaryProgramTemplateItem,
    DailyReport,
    GrowthReference,
    GrowthReferencePoint,
    Supplier,
    Sale,
)
from app.models.billing import Plan, Subscription, PaymentTransaction  # noqa: E402,F401
