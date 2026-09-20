"""Creation d'alertes et declenchement des notifications email (paragraphe 3).

Regle d'envoi (3.2) :
- Alertes urgentes ou importantes (mortalite elevee, stock critique,
  observation urgente) -> email automatique immediat au proprietaire.
- Alertes normales -> pas d'email, consultation dans l'app suffit.
- Le proprietaire peut desactiver les notifications email dans ses parametres.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models.core import ROLE_OWNER, Tenant, User
from app.models.poultry import (
    ALERT_PRIORITY_IMPORTANT,
    ALERT_PRIORITY_NORMAL,
    ALERT_PRIORITY_URGENT,
    Alert,
)
from app.utils.emailing import send_alert_email
from app.utils.tenant import get_current_tenant_id, tenant_bypass

# Valeurs de repli si le tenant n'a pas encore de reglages (ex : cree avant
# l'ajout de /parametres) - les vraies valeurs viennent de Tenant, voir
# _get_tenant() ci-dessous.
DEFAULT_MORTALITY_ALERT_THRESHOLD_PERCENT = 3


def _owners_for_tenant(tenant_id):
    with tenant_bypass():
        return (
            User.query.filter_by(tenant_id=tenant_id, role=ROLE_OWNER, is_active=True)
            .all()
        )


def _get_tenant(tenant_id):
    if tenant_id is None:
        return None
    with tenant_bypass():
        return db.session.get(Tenant, tenant_id)


def create_alert(title, message, alert_type, priority=ALERT_PRIORITY_NORMAL, farm=None, batch=None):
    """Cree une alerte et envoie un email si sa priorite l'exige."""
    tenant_id = get_current_tenant_id()
    alert = Alert(
        tenant_id=tenant_id,
        farm_id=farm.id if farm else (batch.farm_id if batch else None),
        batch_id=batch.id if batch else None,
        title=title,
        message=message,
        type=alert_type,
        priority=priority,
    )
    db.session.add(alert)
    db.session.flush()

    tenant = _get_tenant(tenant_id)
    if alert.requires_email and (tenant is None or tenant.email_alerts_enabled):
        recipients = [
            owner.email
            for owner in _owners_for_tenant(tenant_id)
            if owner.email_notifications_enabled
        ]
        if recipients:
            try:
                send_alert_email(alert, recipients)
                alert.email_sent = True
                alert.email_sent_at = datetime.now(timezone.utc)
            except Exception:
                # Une panne SMTP ne doit jamais bloquer la saisie metier :
                # l'alerte reste visible dans l'application.
                alert.email_sent = False

    return alert


def check_stock_alert(stock_item):
    """Cree une alerte de stock faible si le seuil est franchi (paragraphe 14)."""
    if not stock_item.is_low:
        return None
    return create_alert(
        title=f"Stock faible : {stock_item.name}",
        message=(
            f"Le stock de {stock_item.name} sur la ferme {stock_item.farm.name} "
            f"est descendu a {stock_item.quantity_on_hand} {stock_item.unit} "
            f"(seuil : {stock_item.min_threshold} {stock_item.unit})."
        ),
        alert_type="stock",
        priority=ALERT_PRIORITY_URGENT,
        farm=stock_item.farm,
    )


def check_mortality_alert(batch, batch_day):
    """Cree une alerte si la mortalite du jour depasse le seuil critique
    (configurable par tenant, voir /parametres)."""
    current_count = batch.current_count or 1
    daily_deaths = batch_day.mortality_count
    if daily_deaths <= 0:
        return None

    tenant = _get_tenant(get_current_tenant_id())
    threshold = (
        float(tenant.mortality_alert_threshold_percent)
        if tenant and tenant.mortality_alert_threshold_percent is not None
        else DEFAULT_MORTALITY_ALERT_THRESHOLD_PERCENT
    )

    ratio_percent = (daily_deaths / max(current_count, 1)) * 100
    if ratio_percent < threshold:
        return None

    return create_alert(
        title=f"Mortalite elevee - Lot {batch.code}",
        message=(
            f"{daily_deaths} sujets morts le jour {batch_day.day_number} "
            f"({ratio_percent:.1f} % de l'effectif courant), au-dela du seuil "
            f"de {threshold} %."
        ),
        alert_type="mortality",
        priority=ALERT_PRIORITY_URGENT,
        batch=batch,
    )


def check_total_mortality_alert(batch):
    """Alerte si la mortalite TOTALE du lot depasse nettement ce qui est
    normal pour son type d'elevage (voir species_profiles.py) : le seuil
    quotidien de /parametres ne voit pas une mortalite lente mais reguliere.
    Il faut au moins 5 morts (petits lots), et au plus une alerte par jour."""
    from app.utils.species import get_species

    normal = get_species(batch.species).profile.mortality_normal_percent
    if not batch.initial_count or batch.total_mortality < 5:
        return None
    percent = batch.total_mortality * 100 / batch.initial_count
    if percent <= normal * 1.25:
        return None

    today = datetime.now(timezone.utc).date()
    already_alerted = (
        Alert.query.filter_by(batch_id=batch.id, type="mortality_total")
        .filter(Alert.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc))
        .first()
    )
    if already_alerted:
        return None

    return create_alert(
        title=f"Mortalite totale elevee - Lot {batch.code}",
        message=(
            f"Le lot {batch.code} a perdu {batch.total_mortality} sujets sur {batch.initial_count} "
            f"({percent:.1f} %), alors qu'une mortalite normale pour ce type d'elevage est "
            f"d'environ {normal} % sur un cycle."
        ),
        alert_type="mortality_total",
        priority=ALERT_PRIORITY_IMPORTANT,
        batch=batch,
    )


def check_fcr_alert(batch):
    """Cree une alerte si l'indice de consommation (FCR) du lot depasse le
    seuil defini par le proprietaire (/parametres). Desactive par defaut
    (aucun seuil renseigne) : le FCR normal varie beaucoup selon l'age du
    lot, un seuil errone genererait trop de fausses alertes. Au plus une
    alerte par jour et par lot, pour ne pas spammer a chaque saisie."""
    # Le seuil du proprietaire est pense pour le poulet de chair : les autres
    # especes (pintade, dinde...) ont un indice normal tres different.
    if not batch.is_broiler:
        return None

    tenant = _get_tenant(get_current_tenant_id())
    if not tenant or not tenant.fcr_alert_threshold:
        return None

    from app.utils.zootechnie import compute_fcr

    fcr = compute_fcr(batch)
    if fcr is None or fcr < float(tenant.fcr_alert_threshold):
        return None

    today = datetime.now(timezone.utc).date()
    already_alerted = (
        Alert.query.filter_by(batch_id=batch.id, type="fcr")
        .filter(Alert.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc))
        .first()
    )
    if already_alerted:
        return None

    return create_alert(
        title=f"Aliment par poulet eleve - Lot {batch.code}",
        message=(
            f"Le lot {batch.code} consomme {fcr} kg d'aliment par kg de poulet produit, "
            f"au-dela du seuil de {tenant.fcr_alert_threshold} que vous avez defini."
        ),
        alert_type="fcr",
        priority=ALERT_PRIORITY_IMPORTANT,
        batch=batch,
    )


def check_low_laying_alert(batch):
    """Alerte si le taux de ponte reste nettement sous la courbe attendue
    pendant plusieurs jours de saisie consecutifs (maladie, stress,
    alimentation...). Au plus une alerte par jour et par lot."""
    from app.utils.laying import LOW_LAYING_DAYS, LOW_LAYING_GAP_POINTS
    from app.utils.zootechnie import egg_production_series

    if not batch.is_layer:
        return None
    recent = [p for p in egg_production_series(batch) if p["rate"] is not None][-LOW_LAYING_DAYS:]
    if len(recent) < LOW_LAYING_DAYS or any(p["expected"] is None for p in recent):
        return None
    if any(p["rate"] > p["expected"] - LOW_LAYING_GAP_POINTS for p in recent):
        return None

    today = datetime.now(timezone.utc).date()
    already_alerted = (
        Alert.query.filter_by(batch_id=batch.id, type="laying")
        .filter(Alert.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc))
        .first()
    )
    if already_alerted:
        return None

    avg_rate = sum(p["rate"] for p in recent) / len(recent)
    avg_expected = sum(p["expected"] for p in recent) / len(recent)
    return create_alert(
        title=f"Ponte faible - Lot {batch.code}",
        message=(
            f"Le lot {batch.code} pond {avg_rate:.1f} % ces {len(recent)} derniers jours de saisie, "
            f"contre {avg_expected:.1f} % attendus. Verifiez la sante des poules, l'eau, "
            "l'aliment et le stress (chaleur, bruit)."
        ),
        alert_type="laying",
        priority=ALERT_PRIORITY_IMPORTANT,
        batch=batch,
    )


def check_urgent_observation_alert(observation, batch):
    from app.models.poultry import OBS_SEVERITY_URGENT

    if observation.severity != OBS_SEVERITY_URGENT:
        return None
    return create_alert(
        title=f"Observation urgente - Lot {batch.code}",
        message=observation.description,
        alert_type="observation",
        priority=ALERT_PRIORITY_IMPORTANT,
        batch=batch,
    )


def create_missing_report_alert(batch, batch_day):
    return create_alert(
        title=f"Rapport journalier manquant - Lot {batch.code}",
        message=f"Aucun rapport n'a ete soumis pour le jour {batch_day.day_number}.",
        alert_type="report_missing",
        priority=ALERT_PRIORITY_NORMAL,
        batch=batch,
    )
