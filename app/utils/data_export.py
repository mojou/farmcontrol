"""Export complet des donnees d'un tenant au format JSON.

Objectif "confiance et portabilite" : le proprietaire peut recuperer a tout
moment une copie complete et lisible de ses donnees, independamment de
l'hebergeur (utile en cas de doute sur la disponibilite du service, pour
une sauvegarde personnelle, ou pour migrer ailleurs).

Repose sur le filtre automatique multitenant (app.models.register_tenant_filter) :
chaque requete ci-dessous ne renvoie deja que les lignes du tenant courant,
sans jointure manuelle a ecrire ni risque d'oubli.
"""
from decimal import Decimal

from sqlalchemy import inspect

from app.models import utcnow
from app.models.core import Message, User
from app.models.poultry import (
    BatchDay,
    BatchFinance,
    Batch,
    DailyReport,
    FeedRecord,
    Farm,
    MedicationRecord,
    MortalityRecord,
    Observation,
    SanitaryProgramItem,
    SanitaryProgramTemplateItem,
    StockItem,
    WaterRecord,
    EggRecord,
    WeightRecord,
    WoodRecord,
)

# Champs sensibles ou purement techniques a ne jamais inclure dans un export.
EXCLUDED_FIELDS = {"password_hash", "tenant_id"}


def _model_to_dict(instance):
    mapper = inspect(instance).mapper
    result = {}
    for column in mapper.column_attrs:
        if column.key in EXCLUDED_FIELDS:
            continue
        value = getattr(instance, column.key)
        if isinstance(value, Decimal):
            value = float(value)
        result[column.key] = value
    return result


def build_tenant_export(tenant) -> dict:
    return {
        "export_genere_le": utcnow().isoformat(),
        "compte": _model_to_dict(tenant),
        "utilisateurs": [_model_to_dict(r) for r in User.query.all()],
        "fermes": [_model_to_dict(r) for r in Farm.query.all()],
        "lots": [_model_to_dict(r) for r in Batch.query.all()],
        "jours_de_suivi": [_model_to_dict(r) for r in BatchDay.query.all()],
        "stock": [_model_to_dict(r) for r in StockItem.query.all()],
        "aliment": [_model_to_dict(r) for r in FeedRecord.query.all()],
        "eau": [_model_to_dict(r) for r in WaterRecord.query.all()],
        "oeufs": [_model_to_dict(r) for r in EggRecord.query.all()],
        "mortalite": [_model_to_dict(r) for r in MortalityRecord.query.all()],
        "bois_litiere": [_model_to_dict(r) for r in WoodRecord.query.all()],
        "medicaments": [_model_to_dict(r) for r in MedicationRecord.query.all()],
        "observations": [_model_to_dict(r) for r in Observation.query.all()],
        "pesees": [_model_to_dict(r) for r in WeightRecord.query.all()],
        "rentabilite": [_model_to_dict(r) for r in BatchFinance.query.all()],
        "programme_sanitaire": [_model_to_dict(r) for r in SanitaryProgramItem.query.all()],
        "modele_sanitaire": [_model_to_dict(r) for r in SanitaryProgramTemplateItem.query.all()],
        "rapports_journaliers": [_model_to_dict(r) for r in DailyReport.query.all()],
        "messages": [_model_to_dict(r) for r in Message.query.all()],
    }
