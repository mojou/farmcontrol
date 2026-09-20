"""Ecriture et lecture du journal d'audit (paragraphe 7.3)."""
from flask_babel import lazy_gettext as _l
from flask_login import current_user

from app.extensions import db
from app.models.core import AuditLog
from app.utils.tenant import get_current_tenant_id

# Traduit les noms de table technique en libelle comprehensible par le
# proprietaire sur la page /journal (voir core.audit_log_list).
TABLE_LABELS = {
    "tenants": _l("Compte client"),
    "users": _l("Utilisateur"),
    "farms": _l("Ferme"),
    "poultry_batches": _l("Lot"),
    "poultry_batch_days": _l("Jour de suivi"),
    "poultry_feed_records": _l("Aliment"),
    "poultry_water_records": _l("Eau"),
    "poultry_mortality_records": _l("Mortalite"),
    "poultry_wood_records": _l("Bois / litiere"),
    "poultry_medication_records": _l("Medicament"),
    "poultry_observations": _l("Observation"),
    "poultry_weight_records": _l("Pesee"),
    "poultry_stock_items": _l("Article de stock"),
    "poultry_sanitary_program_items": _l("Programme sanitaire"),
    "poultry_sanitary_program_template_items": _l("Modele sanitaire"),
    "poultry_daily_reports": _l("Rapport journalier"),
    "poultry_batch_finance": _l("Ce que vous gagnez"),
    "billing_subscriptions": _l("Abonnement"),
    "messages": _l("Message"),
    "poultry_sales": _l("Vente"),
    "poultry_suppliers": _l("Fournisseur"),
    "poultry_stock_purchases": _l("Achat de stock"),
}

ACTION_LABELS = {"create": _l("Creation"), "update": _l("Modification"), "delete": _l("Suppression")}


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
