"""Programme sanitaire de reference et feuille de route pour le poulet de
chair (vaccination, traitements, alimentation, eau de boisson).

Sources (programme indicatif, a adapter avec un veterinaire local et selon
les produits reellement disponibles / les instructions du couvoir) :
- CEVA Sante Animale Afrique, "Programme de vaccination poulet de chair"
  (https://www.ceva-africa.com)
- GIZ - NAFA (formation avicole, Cameroun), "Protocole de vaccination et de
  traitement du poulet de chair moderne" et "Consommation journaliere d'eau
  et d'aliment du poulet de chair moderne" (https://nafa-formation.org)

Ces deux sources convergent sur un meme calendrier J1-J21 (Newcastle +
bronchite infectieuse, Gumboro simple puis fort, rappel Newcastle/bronchite),
complete par les phases d'alimentation demarrage/croissance/finition.

Les produits de complementation (Bio Select, Harmony, Belgo Fresh, Belgo
Protect, Belgo Thermo, Belgo Vitesse, Belgo Dry Litter, vermifuge) sont
positionnes a des jours coherents avec leur fonction habituelle (probiotique,
anti-stress, qualite de l'eau, soutien immunitaire, gestion de la chaleur,
croissance, litiere, deparasitage), mais leur posologie exacte n'a pas pu
etre verifiee aupres d'une fiche technique fiable au moment de la redaction :
elle doit imperativement etre reprise depuis l'etiquette/notice du produit
reellement utilise (voir DOSAGE_A_VERIFIER dans les notes correspondantes).
"""
from datetime import date, timedelta

from app.extensions import db
from app.models.poultry import SanitaryProgramItem

DOSAGE_A_VERIFIER = (
    " [Posologie non verifiee par l'application - se referer imperativement "
    "a l'etiquette/notice du produit reellement utilise avant administration.]"
)

# -- Programme sanitaire et alimentaire de reference (jour = BatchDay.day_number, J1 = mise en place) --

DEFAULT_SANITARY_PROGRAM = [
    {
        "day_number": 1,
        "program_type": "alimentation",
        "product_name": "Eau sucree + demarrage aliment demarrage",
        "notes": (
            "Des l'arrivee : eau sucree (20 g de sucre par litre d'eau de boisson) pour lutter "
            "contre le stress du transport et la deshydratation. Debuter l'aliment chair "
            "demarrage (jusqu'au jour 14)."
        ),
    },
    {
        "day_number": 1,
        "program_type": "complement",
        "product_name": "Bio Select (probiotique)",
        "notes": (
            "A donner des le 1er jour dans l'eau de boisson pour installer une flore intestinale "
            "saine chez le poussin. A renouveler apres toute cure d'anti-infectieux/antibiotique "
            "(voir rappel J6)." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 1,
        "program_type": "complement",
        "product_name": "Belgo Fresh (conditionneur d'eau)",
        "notes": (
            "A ajouter regulierement a l'eau de boisson pendant tout le cycle pour ameliorer sa "
            "qualite et l'appetence, en particulier en saison chaude." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 1,
        "program_type": "traitement",
        "product_name": "Anti-infectieux + vitamines (J1 a J5)",
        "notes": (
            "A administrer dans l'eau de boisson du 1er au 5e jour pour prevenir les infections "
            "de demarrage. Respecter la posologie indiquee sur la notice du produit utilise."
        ),
    },
    {
        "day_number": 3,
        "program_type": "vaccination",
        "product_name": "Newcastle + Bronchite infectieuse (HB1 / H120)",
        "notes": (
            "Vaccin en eau de boisson (ou deja fait par spray/injection au couvoir - dans ce cas "
            "ne pas revacciner). Retirer l'eau 1h a 1h30 avant, puis diluer le vaccin dans la "
            "quantite d'eau que le lot boit normalement en 1 a 2 heures. Anti-stress avant et "
            "apres la vaccination."
        ),
    },
    {
        "day_number": 3,
        "program_type": "complement",
        "product_name": "Harmony (anti-stress)",
        "notes": (
            "Anti-stress a donner avant et apres chaque vaccination (voir aussi J7, J14, "
            "J18)." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 6,
        "program_type": "complement",
        "product_name": "Bio Select (rappel probiotique)",
        "notes": (
            "Rappel juste apres la cure d'anti-infectieux du J1-J5 pour restaurer la flore "
            "intestinale." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 7,
        "program_type": "vaccination",
        "product_name": "Gumboro - souche intermediaire (1ere dose)",
        "notes": (
            "Vaccin en eau de boisson, meme protocole (assoiffer 1h-1h30 puis diluer dans l'eau "
            "consommee en 2h, avec un peu de lait en poudre si recommande par le fabricant). "
            "Ne pas faire si vaccination Gumboro deja realisee au couvoir par injection."
        ),
    },
    {
        "day_number": 7,
        "program_type": "complement",
        "product_name": "Harmony + Belgo Protect (anti-stress et soutien immunitaire)",
        "notes": (
            "A associer a la vaccination Gumboro pour reduire le stress et soutenir la reponse "
            "immunitaire." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 7,
        "program_type": "complement",
        "product_name": "Belgo Dry Litter (litiere)",
        "notes": (
            "Controler l'etat de la litiere (humidite, odeur d'ammoniac) et traiter si "
            "necessaire. A renouveler chaque semaine (voir J14, J21, J28)." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 14,
        "program_type": "vaccination",
        "product_name": "Gumboro - souche forte / intermediaire plus (rappel)",
        "notes": "Rappel Gumboro en eau de boisson, meme protocole d'assoiffement puis dilution.",
    },
    {
        "day_number": 14,
        "program_type": "traitement",
        "product_name": "Anticoccidien (J14 a J18)",
        "notes": "Traitement anticoccidien en eau de boisson pendant 3 a 5 jours (coccidiose).",
    },
    {
        "day_number": 14,
        "program_type": "complement",
        "product_name": "Harmony + Belgo Protect (anti-stress et soutien immunitaire)",
        "notes": "A associer au rappel Gumboro, meme logique qu'au jour 7." + DOSAGE_A_VERIFIER,
    },
    {
        "day_number": 14,
        "program_type": "complement",
        "product_name": "Belgo Dry Litter (litiere)",
        "notes": "Controle hebdomadaire de la litiere." + DOSAGE_A_VERIFIER,
    },
    {
        "day_number": 15,
        "program_type": "alimentation",
        "product_name": "Passage a l'aliment croissance",
        "notes": "Aliment chair croissance du jour 15 au jour 28.",
    },
    {
        "day_number": 15,
        "program_type": "complement",
        "product_name": "Belgo Vitesse (activateur de croissance)",
        "notes": (
            "A partir du passage en phase croissance, pour soutenir la vitesse de croissance "
            "(voir aussi J29)." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 18,
        "program_type": "vaccination",
        "product_name": "Rappel Newcastle + Bronchite infectieuse (Lasota / H120)",
        "notes": (
            "Rappel en eau de boisson. Prevoir environ 15 litres d'eau vaccinale pour 1000 "
            "sujets (a adapter au prorata de l'effectif reel du lot)."
        ),
    },
    {
        "day_number": 18,
        "program_type": "complement",
        "product_name": "Harmony (anti-stress)",
        "notes": "A associer au rappel Newcastle/Bronchite, meme logique qu'aux jours precedents." + DOSAGE_A_VERIFIER,
    },
    {
        "day_number": 21,
        "program_type": "complement",
        "product_name": "Belgo Dry Litter (litiere)",
        "notes": "Controle hebdomadaire de la litiere." + DOSAGE_A_VERIFIER,
    },
    {
        "day_number": 22,
        "program_type": "complement",
        "product_name": "Belgo Thermo (gestion du stress thermique)",
        "notes": (
            "Les sujets plus lourds supportent moins bien la chaleur : a utiliser en periode "
            "chaude ou en cas de forte densite/ventilation insuffisante." + DOSAGE_A_VERIFIER
        ),
    },
    {
        "day_number": 28,
        "program_type": "complement",
        "product_name": "Belgo Dry Litter (litiere)",
        "notes": "Controle hebdomadaire de la litiere avant la phase de finition." + DOSAGE_A_VERIFIER,
    },
    {
        "day_number": 29,
        "program_type": "alimentation",
        "product_name": "Passage a l'aliment finition",
        "notes": "Aliment chair finition a partir du jour 29 jusqu'a la sortie du lot.",
    },
    {
        "day_number": 29,
        "program_type": "complement",
        "product_name": "Belgo Vitesse (rappel croissance/finition)",
        "notes": "Rappel pour soutenir la croissance en phase de finition." + DOSAGE_A_VERIFIER,
    },
    {
        "day_number": 29,
        "program_type": "traitement",
        "product_name": "Vermifuge / deparasitage (si necessaire)",
        "notes": (
            "Deparasitage en dose unique en cas de suspicion de parasitisme. Eviter les "
            "traitements lourds en fin de cycle : respecter le delai d'attente avant l'abattage."
        ),
    },
]

# Consommation moyenne par semaine d'age (GIZ-Nafa, poulet de chair moderne) :
# {semaine: (poids_moyen_g, aliment_g_par_jour_par_sujet, eau_ml_par_jour_par_sujet)}
WEEKLY_CONSUMPTION_REFERENCE = {
    1: (160, 30, 50),
    2: (430, 60, 80),
    3: (840, 105, 120),
    4: (1390, 155, 160),
    5: (2010, 185, 190),
    6: (2625, 200, 240),
    7: (3175, 205, 280),
    8: (3640, 200, 320),
}
MAX_REFERENCE_WEEK = max(WEEKLY_CONSUMPTION_REFERENCE)


def _week_for_day(day_number: int) -> int:
    week = ((max(day_number, 1) - 1) // 7) + 1
    return min(week, MAX_REFERENCE_WEEK)


def estimate_daily_water_liters(batch, day_number: int) -> float:
    """Estimation du volume d'eau de boisson (litres) pour tout le lot, un jour donne."""
    _, _, ml_per_bird = WEEKLY_CONSUMPTION_REFERENCE[_week_for_day(day_number)]
    return round((ml_per_bird * (batch.current_count or 0)) / 1000, 1)


def estimate_daily_feed_kg(batch, day_number: int) -> float:
    """Estimation de la quantite d'aliment (kg) pour tout le lot, un jour donne."""
    _, g_per_bird, _ = WEEKLY_CONSUMPTION_REFERENCE[_week_for_day(day_number)]
    return round((g_per_bird * (batch.current_count or 0)) / 1000, 1)


def current_batch_day_number(batch) -> int:
    """Numero de jour du lot a la date du jour (1 = jour de mise en place)."""
    return (date.today() - batch.start_date).days + 1


def seed_default_sanitary_program(batch):
    """Cree les elements du programme sanitaire de reference pour un lot qui
    vient d'etre creee. N'ecrase rien si le lot a deja des elements (evite
    les doublons en cas de nouvel appel)."""
    if batch.sanitary_items:
        return

    for item in DEFAULT_SANITARY_PROGRAM:
        db.session.add(
            SanitaryProgramItem(
                tenant_id=batch.tenant_id,
                batch_id=batch.id,
                day_number=item["day_number"],
                program_type=item["program_type"],
                product_name=item["product_name"],
                notes=item["notes"],
            )
        )


def get_pending_items(batch, upto_day: int = None):
    """Elements du programme non realises dont le jour est atteint ou depasse."""
    upto_day = upto_day if upto_day is not None else current_batch_day_number(batch)
    return sorted(
        (item for item in batch.sanitary_items if not item.is_done and item.day_number <= upto_day),
        key=lambda item: item.day_number,
    )


def get_worker_reminder(user):
    """Prochaine tache sanitaire en attente pour les lots actifs accessibles
    a l'utilisateur (sa ferme s'il en a une assignee, sinon toutes celles du
    tenant). Retourne None si rien n'est en attente."""
    from app.models.poultry import BATCH_STATUS_ACTIVE, Batch, Farm

    farms_query = Farm.query
    if user.farm_id:
        farms_query = farms_query.filter_by(id=user.farm_id)
    farm_ids = [f.id for f in farms_query.all()]
    if not farm_ids:
        return None

    active_batches = Batch.query.filter(Batch.farm_id.in_(farm_ids), Batch.status == BATCH_STATUS_ACTIVE).all()

    best_item = None
    best_batch = None
    for batch in active_batches:
        pending = get_pending_items(batch)
        if pending and (best_item is None or pending[0].day_number < best_item.day_number):
            best_item = pending[0]
            best_batch = batch

    if best_item is None:
        return None
    return {"item": best_item, "batch": best_batch}
