"""Reperes techniques par type d'elevage (la "fiche" de chaque type).

Ces chiffres sont des ORDRES DE GRANDEUR pour situer un lot (est-il dans la
norme ?), pas des objectifs garantis : ils varient selon la souche, l'aliment,
le climat et la conduite d'elevage. Le proprietaire garde la main : il peut
creer ses propres courbes de poids ("Poids normal attendu") avec les chiffres
de son fournisseur.

Origine des valeurs (voir SOURCES) : "litterature" = releve dans les
publications listees ; "indicatif" = valeur courante de la filiere, a
verifier avec votre fournisseur ou votre veterinaire. Aucun calendrier de
vaccination n'est fourni : il depend de la zone et se definit avec un
veterinaire.

Poids en grammes partout (les porcs et les dindes s'affichent en kg).
"""
from dataclasses import dataclass, field

from flask_babel import lazy_gettext as _l


@dataclass(frozen=True)
class Curve:
    name: str              # nom stocke en base (francais) - voir _CURVE_NAME_MARKERS
    points: tuple          # ((jour d'age, poids en grammes), ...)


@dataclass(frozen=True)
class Profile:
    weight_unit: str = "g"                 # unite de saisie et d'affichage des pesees
    market_weight_g: tuple = (0, 0)        # poids de vente habituel (mini, maxi) en grammes
    fcr_range: tuple = None                # aliment (kg) par kg de poids produit, plage normale
    mortality_normal_percent: float = 5    # mortalite totale normale sur un cycle (%)
    notes: object = ""                     # particularites de ce type d'elevage
    curves: tuple = field(default_factory=tuple)   # courbes de poids standard indicatives
    sources_ids: tuple = ()                # numeros dans SOURCES
    verified: bool = False                 # chiffres releves dans la litterature (vs indicatifs)


# Poulet de chair : moyennes hebdomadaires GIZ - NAFA (deja utilisees pour les estimations)
_BROILER = ((7, 160), (14, 430), (21, 840), (28, 1390), (35, 2010), (42, 2625), (49, 3175), (56, 3640))

PROFILES = {
    "broiler": Profile(
        market_weight_g=(1800, 2800), fcr_range=(1.6, 2.1), mortality_normal_percent=4,
        notes=_l("Cycle court (5 a 7 semaines). Croissance tres rapide : la moindre baisse d'aliment ou d'eau se voit vite sur le poids."),
        curves=(Curve("Poulet de chair standard (GIZ-NAFA)", _BROILER),), sources_ids=(1, 2), verified=True,
    ),
    "layer": Profile(
        market_weight_g=(1500, 2000), fcr_range=None, mortality_normal_percent=8,
        notes=_l("Le suivi porte sur la ponte : taux de ponte compare a la courbe attendue selon l'age des poules. Les poules pondent a partir de 18 a 20 semaines environ."),
        sources_ids=(2,), verified=False,
    ),
    "guinea_fowl": Profile(
        market_weight_g=(1200, 1600), fcr_range=(2.5, 4.2), mortality_normal_percent=5,
        notes=_l("Croissance plus lente que le poulet de chair : l'aliment par kilo produit augmente beaucoup avec l'age (environ 2,5 a 8 semaines, plus de 4 a 14 semaines). Vendre tot est plus rentable."),
        curves=(Curve("Pintade standard (indicatif)", ((28, 320), (56, 700), (84, 1200), (98, 1350), (112, 1450), (126, 1550))),),
        sources_ids=(3,), verified=True,
    ),
    "turkey": Profile(
        weight_unit="kg", market_weight_g=(8000, 16000), fcr_range=(2.0, 3.0), mortality_normal_percent=8,
        notes=_l("Males et femelles n'ont pas le meme poids : les femelles (dindes) sont vendues vers 14 a 18 semaines, les males (dindons) plus tard et beaucoup plus lourds. Les jeunes dindonneaux sont fragiles les premieres semaines."),
        curves=(Curve("Dinde standard (indicatif, moyenne males et femelles)", ((28, 1100), (56, 3800), (84, 7500), (98, 10000), (112, 11500), (126, 13000))),),
        sources_ids=(4,), verified=True,
    ),
    "duck": Profile(
        market_weight_g=(2200, 3200), fcr_range=(2.5, 3.0), mortality_normal_percent=5,
        notes=_l("Le canard de Pekin est vendu vers 7 a 9 semaines ; le canard de Barbarie (Muscovy) est plus lent (10 a 12 semaines) et le male est bien plus lourd que la femelle."),
        curves=(Curve("Canard de Pekin standard (indicatif)", ((14, 450), (28, 1100), (42, 1900), (56, 2500), (70, 2900))),),
        sources_ids=(5,), verified=True,
    ),
    "quail": Profile(
        market_weight_g=(150, 200), fcr_range=(3.0, 3.6), mortality_normal_percent=8,
        notes=_l("Cycle tres court (6 semaines pour la viande). Les cailles pondeuses commencent a pondre vers 6 a 7 semaines."),
        curves=(Curve("Caille du Japon standard (indicatif)", ((7, 28), (14, 65), (21, 100), (28, 130), (35, 150), (42, 165))),),
        sources_ids=(6,), verified=True,
    ),
    "pig": Profile(
        weight_unit="kg", market_weight_g=(90000, 115000), fcr_range=(2.8, 3.5), mortality_normal_percent=5,
        notes=_l("Le porc gagne environ 0,7 a 0,8 kg par jour en croissance. Chez les petits eleveurs le cycle est souvent plus long qu'en elevage industriel. Ce suivi couvre l'engraissement, pas la reproduction (truies, portees)."),
        curves=(Curve("Porc d'engraissement standard (indicatif)", ((28, 7000), (56, 17000), (84, 32000), (112, 52000), (140, 75000), (168, 100000), (196, 122000))),),
        sources_ids=(7,), verified=True,
    ),
    "rabbit": Profile(
        market_weight_g=(2200, 2700), fcr_range=(2.8, 3.5), mortality_normal_percent=10,
        notes=_l("Les lapereaux sont fragiles apres le sevrage (diarrhees, problemes respiratoires) : une mortalite de 10 pour cent est consideree normale en engraissement. Ce suivi couvre l'engraissement, pas les lapines reproductrices."),
        curves=(Curve("Lapin standard (indicatif)", ((35, 850), (56, 1750), (70, 2250), (84, 2500), (98, 2800))),),
        sources_ids=(8,), verified=True,
    ),
    "fish": Profile(
        market_weight_g=(350, 1000), fcr_range=(1.2, 2.1), mortality_normal_percent=10,
        notes=_l("Le poisson vit dans l'eau : pas de rubrique eau de boisson ni litiere. La qualite de l'eau (oxygene, temperature) n'est pas suivie ici. Le silure (Clarias) grossit plus vite que le tilapia mais demande un aliment plus riche en proteines."),
        curves=(
            Curve("Tilapia standard (indicatif)", ((30, 8), (60, 30), (90, 80), (120, 160), (150, 260), (180, 380))),
            Curve("Silure Clarias standard (indicatif)", ((30, 12), (60, 60), (90, 160), (120, 300), (150, 500), (180, 750))),
        ),
        sources_ids=(9,), verified=True,
    ),
}

# Textes des noms de courbes : stockes en base en francais, traduits a l'affichage
# (marqueurs pour l'extraction des traductions, comme pour la courbe de ponte).
_CURVE_NAME_MARKERS = (
    _l("Poulet de chair standard (GIZ-NAFA)"),
    _l("Pintade standard (indicatif)"),
    _l("Dinde standard (indicatif, moyenne males et femelles)"),
    _l("Canard de Pekin standard (indicatif)"),
    _l("Caille du Japon standard (indicatif)"),
    _l("Porc d'engraissement standard (indicatif)"),
    _l("Lapin standard (indicatif)"),
    _l("Tilapia standard (indicatif)"),
    _l("Silure Clarias standard (indicatif)"),
)

# Publications consultees (numeros references par Profile.sources_ids)
SOURCES = {
    1: ("GIZ - NAFA : consommation journaliere d'eau et d'aliment du poulet de chair moderne", "https://nafa-formation.org"),
    2: ("Mortalite et performances des poulets de chair et des pondeuses (Poult. Sci., PMC)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC9583157/"),
    3: ("Croissance de la pintade en elevage intensif et libre (PMC, Academia)", "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10636083/"),
    4: ("Dinde BUT Big 6 : indices de consommation et poids (Poultry Site, Penn State Extension)", "https://extension.psu.edu/small-flock-turkey-production"),
    5: ("Canards Pekin, Barbarie et Mulard : poids et indice de consommation (LRRD)", "https://www.lrrd.org/lrrd18/11/solo18154.htm"),
    6: ("Caille du Japon : poids, ponte et indice de consommation (PMC)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10113653/"),
    7: ("Croissance et indice de consommation du porc a l'engrais (Pork Information Gateway, PubMed)", "https://pubmed.ncbi.nlm.nih.gov/9820889/"),
    8: ("Lapin de chair : poids, indice de consommation et mortalite (J. Anim. Sci., PMC)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC6431822/"),
    9: ("Tilapia du Nil et silure africain : croissance, indice de consommation, survie (FAO, PMC)", "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12750505/"),
}


def profile_for(code):
    return PROFILES.get(code) or PROFILES["broiler"]
