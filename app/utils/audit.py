"""Ecriture dans le journal d'audit (paragraphe 7.3)."""
from flask_login import current_user

from app.extensions import db
from app.models.core import AuditLog
from app.utils.tenant import get_current_tenant_id


def log_action(action: str, table_name: str, record_id=None, details: dict = None):
    """Enregistre une entree d'audit. A appeler apres commit ou dans la meme
    transaction (le log est ajoute a la session courante, non commite ici).
    """
    try:
        user_id = current_user.id if current_user and current_user.is_authenticated else None
    except Exception:
        user_id = None

    entry = AuditLog(
        tenant_id=get_current_tenant_id(),
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        details=details or {},
    )
    db.session.add(entry)
