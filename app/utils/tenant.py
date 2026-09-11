"""Gestion du contexte tenant courant (isolation multitenant - couche applicative).

Ce module fournit le mecanisme de filtrage automatique par tenant_id sur
toutes les requetes SQLAlchemy (couche 1 de securite decrite au paragraphe 7.1
du cahier des charges). La couche 2 (Row Level Security PostgreSQL) est geree
en complement dans app/utils/rls.py.
"""
import contextvars
from contextlib import contextmanager

from flask import g, has_request_context

_tenant_ctx: contextvars.ContextVar = contextvars.ContextVar("current_tenant_id", default=None)
_bypass_ctx: contextvars.ContextVar = contextvars.ContextVar("tenant_rls_bypass", default=False)


def set_current_tenant(tenant_id):
    """Definit le tenant courant pour la requete/le script en cours."""
    if has_request_context():
        g.tenant_id = tenant_id
    _tenant_ctx.set(tenant_id)


def get_current_tenant_id():
    if has_request_context() and getattr(g, "tenant_id", None) is not None:
        return g.tenant_id
    return _tenant_ctx.get()


def set_tenant_bypass(value: bool):
    if has_request_context():
        g.tenant_bypass = value
    _bypass_ctx.set(value)


def is_tenant_bypassed() -> bool:
    if has_request_context() and getattr(g, "tenant_bypass", None) is not None:
        return g.tenant_bypass
    return _bypass_ctx.get()


def _sync_rls_session_vars():
    """Repercute le contexte tenant courant sur la session PostgreSQL.

    Necessaire en dehors d'une requete HTTP (commandes `flask ...`, scripts) :
    le hook `before_request` (app/utils/rls.py) ne s'execute alors pas, mais
    la RLS PostgreSQL (couche 2, paragraphe 7.2) reste active et bloquerait
    silencieusement toute ecriture si les variables de session ne sont pas
    positionnees. Sans effet si aucun contexte applicatif/session DB n'est
    disponible (ex. tests unitaires purs).
    """
    try:
        from sqlalchemy import text

        from app.extensions import db

        tenant_id = get_current_tenant_id()
        db.session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, false)"),
            {"tenant_id": str(tenant_id) if tenant_id is not None else "-1"},
        )
        db.session.execute(
            text("SELECT set_config('app.is_superadmin', :flag, false)"),
            {"flag": "true" if is_tenant_bypassed() else "false"},
        )
    except Exception:
        pass


@contextmanager
def tenant_bypass():
    """Contexte permettant a un super-administrateur de requeter tous les tenants.

    A utiliser avec parcimonie, uniquement dans les vues reservees au role
    super_admin (panneau d'administration de la plateforme), ou dans les
    scripts/commandes CLI d'administration de la plateforme.
    """
    previous = is_tenant_bypassed()
    set_tenant_bypass(True)
    _sync_rls_session_vars()
    try:
        yield
    finally:
        set_tenant_bypass(previous)
        _sync_rls_session_vars()


@contextmanager
def tenant_context(tenant_id):
    """Contexte pour executer du code (scripts, taches) sous un tenant donne."""
    previous = get_current_tenant_id()
    set_current_tenant(tenant_id)
    _sync_rls_session_vars()
    try:
        yield
    finally:
        set_current_tenant(previous)
        _sync_rls_session_vars()
