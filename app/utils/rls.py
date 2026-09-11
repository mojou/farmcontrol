"""Row Level Security PostgreSQL - couche 2 de securite (paragraphe 7.2).

Ce module synchronise, a chaque requete, la variable de session PostgreSQL
`app.current_tenant` (et `app.is_superadmin`) utilisee par les politiques RLS
definies dans scripts/enable_rls.sql. Meme si le filtre applicatif
(app/models/__init__.py) est omis par erreur sur une requete, PostgreSQL
refusera de retourner les lignes d'un autre tenant.
"""
from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.utils.tenant import get_current_tenant_id, is_tenant_bypassed


def sync_rls_session(is_super_admin: bool = False):
    """Positionne les variables de session PostgreSQL pour la connexion en cours."""
    if not current_app.config.get("ENFORCE_RLS", True):
        return

    tenant_id = get_current_tenant_id()
    bypass = is_tenant_bypassed() or is_super_admin

    db.session.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, false)"),
        {"tenant_id": str(tenant_id) if tenant_id is not None else "-1"},
    )
    db.session.execute(
        text("SELECT set_config('app.is_superadmin', :flag, false)"),
        {"flag": "true" if bypass else "false"},
    )


def reset_rls_session():
    if not current_app.config.get("ENFORCE_RLS", True):
        return
    db.session.execute(text("SELECT set_config('app.current_tenant', '-1', false)"))
    db.session.execute(text("SELECT set_config('app.is_superadmin', 'false', false)"))
