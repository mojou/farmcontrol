"""Types d'elevage supportes et vocabulaire associe.

Chaque lot a un type (poulet de chair par defaut). Tous partagent la meme
logique de suivi (effectif, aliment, eau, mortalite, pesees, ventes,
calendrier des soins) : seuls changent le vocabulaire affiche ("poulets",
"porcs", "poissons"...), la duree de cycle habituelle et quelques rubriques
qui n'ont pas de sens partout (pas de litiere ni d'eau de boisson pour des
poissons). Les calculs propres au poulet de chair (estimation de la
consommation journaliere, alerte sur l'indice de consommation) ne
s'appliquent qu'a ce type, faute de reference fiable pour les autres.

Le proprietaire choisit dans /parametres les types qu'il pratique
(Tenant.enabled_species) et son type principal (Tenant.primary_species) :
c'est ce qui filtre la liste proposee a la creation d'un lot et ce qui
determine le vocabulaire des pages qui ne concernent pas un lot precis.
"""
from dataclasses import dataclass

from flask_babel import lazy_gettext as _l

SPECIES_BROILER = "broiler"
SPECIES_LAYER = "layer"
SPECIES_GUINEA_FOWL = "guinea_fowl"
SPECIES_TURKEY = "turkey"
SPECIES_DUCK = "duck"
SPECIES_QUAIL = "quail"
SPECIES_PIG = "pig"
SPECIES_RABBIT = "rabbit"
SPECIES_FISH = "fish"

DEFAULT_SPECIES = SPECIES_BROILER


@dataclass(frozen=True)
class Species:
    code: str
    label: object          # nom du type d'elevage (ex : "Poulet de chair")
    animals: object        # pluriel (ex : "poulets")
    animal: object         # singulier (ex : "poulet")
    young: object          # jeunes animaux achetes (ex : "poussins")
    cycle_days: int        # duree de cycle habituelle, pour pre-remplir la cloture
    uses_litter: bool = True       # rubrique "Bois / litiere"
    drinks_water: bool = True      # rubrique "Eau de boisson"


SPECIES = [
    Species(SPECIES_BROILER, _l("Poulet de chair"), _l("poulets"), _l("poulet"), _l("poussins"), 42),
    Species(SPECIES_LAYER, _l("Poule pondeuse"), _l("poules"), _l("poule"), _l("poussins"), 540),
    Species(SPECIES_GUINEA_FOWL, _l("Pintade"), _l("pintades"), _l("pintade"), _l("poussins"), 90),
    Species(SPECIES_TURKEY, _l("Dinde"), _l("dindes"), _l("dinde"), _l("poussins"), 120),
    Species(SPECIES_DUCK, _l("Canard"), _l("canards"), _l("canard"), _l("poussins"), 70),
    Species(SPECIES_QUAIL, _l("Caille"), _l("cailles"), _l("caille"), _l("poussins"), 45),
    Species(SPECIES_PIG, _l("Porc d'engraissement"), _l("porcs"), _l("porc"), _l("porcelets"), 180),
    Species(SPECIES_RABBIT, _l("Lapin"), _l("lapins"), _l("lapin"), _l("lapereaux"), 90),
    Species(SPECIES_FISH, _l("Poisson (tilapia, silure...)"), _l("poissons"), _l("poisson"), _l("alevins"), 180,
            uses_litter=False, drinks_water=False),
]

SPECIES_BY_CODE = {s.code: s for s in SPECIES}
ALL_CODES = [s.code for s in SPECIES]

# (code stocke en base, libelle affiche) - pour les listes deroulantes
SPECIES_CHOICES = [(s.code, s.label) for s in SPECIES]
SPECIES_LABELS = {s.code: s.label for s in SPECIES}

# Mot neutre quand plusieurs types sont pratiques (pages qui melangent les lots)
GENERIC_ANIMALS = _l("animaux")
GENERIC_ANIMAL = _l("animal")
GENERIC_YOUNG = _l("jeunes animaux")


def get_species(code):
    return SPECIES_BY_CODE.get(code) or SPECIES_BY_CODE[DEFAULT_SPECIES]


def parse_enabled(value):
    """'broiler,layer' -> ['broiler', 'layer'] (codes inconnus ignores)."""
    codes = [c.strip() for c in (value or "").split(",")]
    return [c for c in ALL_CODES if c in codes]


def serialize_enabled(codes):
    """Codes valides, dans l'ordre du catalogue, separes par des virgules."""
    wanted = set(codes or [])
    return ",".join(c for c in ALL_CODES if c in wanted)


def choices_for(enabled_codes, always_include=None):
    """Choix de type d'elevage proposes : types actives + (optionnel) celui
    d'un lot existant, meme s'il a ete desactive depuis."""
    keep = set(enabled_codes or [DEFAULT_SPECIES])
    if always_include:
        keep.add(always_include)
    return [(s.code, s.label) for s in SPECIES if s.code in keep]


def cycle_days_for(species_code, tenant=None):
    """Duree de cycle proposee a la cloture d'un lot : le reglage de
    l'exploitation s'il existe et que le lot est de son type principal,
    sinon la duree habituelle du type d'elevage."""
    if (
        tenant is not None
        and getattr(tenant, "default_cycle_days", None)
        and species_code == getattr(tenant, "primary_species", DEFAULT_SPECIES)
    ):
        return tenant.default_cycle_days
    return get_species(species_code).cycle_days


def _tenant_species(tenant):
    """Type unique pratique par l'exploitation, ou None s'il y en a plusieurs."""
    codes = parse_enabled(getattr(tenant, "enabled_species", None)) if tenant else []
    return get_species(codes[0]) if len(codes) == 1 else None


def _resolve(target, tenant=None):
    """`target` : un lot, un code de type, ou None (= vocabulaire de l'exploitation)."""
    if target is None:
        return _tenant_species(tenant)
    code = getattr(target, "species", target)
    return get_species(code)


def animals_term(target=None, tenant=None):
    sp = _resolve(target, tenant)
    return sp.animals if sp else GENERIC_ANIMALS


def animal_term(target=None, tenant=None):
    sp = _resolve(target, tenant)
    return sp.animal if sp else GENERIC_ANIMAL


def young_term(target=None, tenant=None):
    sp = _resolve(target, tenant)
    return sp.young if sp else GENERIC_YOUNG


def de_term(term):
    """Precede un mot de "de" avec l'elision francaise ("de porcs",
    "d'animaux", "d'alevins"). En anglais, renvoie le mot seul : la
    traduction du gabarit porte elle-meme le "of"."""
    from flask_babel import get_locale

    text = str(term)
    locale = get_locale()
    if locale is not None and locale.language != "fr":
        return text
    return ("d'" if text[:1].lower() in "aeiouyhàâéèêîïôû" else "de ") + text
