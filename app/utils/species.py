"""Types d'elevage supportes.

Chaque lot a un type (poulet de chair par defaut). Toutes les volailles
partagent la meme logique de suivi (effectif, aliment, eau, mortalite,
pesees, ventes, calendrier des soins) : seul le libelle change, ainsi que
quelques calculs propres au poulet de chair (estimation de la consommation
journaliere, alerte sur l'indice de consommation) qui ne s'appliquent pas
aux autres especes tant qu'aucune reference fiable n'existe pour elles.
"""
from flask_babel import lazy_gettext as _l

SPECIES_BROILER = "broiler"
SPECIES_GUINEA_FOWL = "guinea_fowl"
SPECIES_TURKEY = "turkey"
SPECIES_DUCK = "duck"
SPECIES_QUAIL = "quail"

DEFAULT_SPECIES = SPECIES_BROILER

# (code stocke en base, libelle affiche)
SPECIES_CHOICES = [
    (SPECIES_BROILER, _l("Poulet de chair")),
    (SPECIES_GUINEA_FOWL, _l("Pintade")),
    (SPECIES_TURKEY, _l("Dinde")),
    (SPECIES_DUCK, _l("Canard")),
    (SPECIES_QUAIL, _l("Caille")),
]

SPECIES_LABELS = dict(SPECIES_CHOICES)
