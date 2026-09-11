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


@contextmanager
def tenant_bypass():
    """Contexte permettant a un super-administrateur de requeter tous les tenants.

    A utiliser avec parcimonie, uniquement dans les vues reservees au role
    super_admin (panneau d'administration de la plateforme).
    """
    previous = is_tenant_bypassed()
    set_tenant_bypass(True)
    try:
        yield
    finally:
        set_tenant_bypass(previous)


@contextmanager
def tenant_context(tenant_id):
    """Contexte pour executer du code (scripts, taches) sous un tenant donne."""
    previous = get_current_tenant_id()
    set_current_tenant(tenant_id)
    try:
        yield
    finally:
        set_current_tenant(previous)
