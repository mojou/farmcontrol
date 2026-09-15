"""Ecriture et lecture du journal d'audit (paragraphe 7.3)."""
from flask_login import current_user

from app.extensions import db
from app.models.core import AuditLog
from app.utils.tenant import get_current_tenant_id

# Traduit les noms de table technique en libelle comprehensible par le
# proprietaire sur la page /journal (voir core.audit_log_list).
TABLE_LABELS = {
    "tenants": "Compte client",
    "users": "Utilisateur",
    "farms": "Ferme",
    "poultry_batches": "Lot",
    "poultry_batch_days": "Jour de suivi",
    "poultry_feed_records": "Aliment",
    "poultry_water_records": "Eau",
    "poultry_mortality_records": "Mortalite",
    "poultry_wood_records": "Bois / litiere",
    "poultry_medication_records": "Medicament",
    "poultry_observations": "Observation",
    "poultry_weight_records": "Pesee",
    "poultry_stock_items": "Article de stock",
    "poultry_sanitary_program_items": "Programme sanitaire",
    "poultry_sanitary_program_template_items": "Modele sanitaire",
    "poultry_daily_reports": "Rapport journalier",
    "poultry_batch_finance": "Rentabilite",
    "billing_subscriptions": "Abonnement",
    "messages": "Message",
    "poultry_sales": "Vente",
    "poultry_suppliers": "Fournisseur",
}

ACTION_LABELS = {"create": "Creation", "update": "Modification", "delete": "Suppression"}


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
