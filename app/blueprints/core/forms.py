from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DecimalField, IntegerField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from app.models.core import ROLE_LABELS, ROLE_MANAGER, ROLE_WORKER


class TenantForm(FlaskForm):
    name = StringField(_l("Nom de l'exploitation / client"), validators=[DataRequired(), Length(max=150)])
    slug = StringField(_l("Identifiant (slug)"), validators=[DataRequired(), Length(max=80)])
    plan = SelectField(
        _l("Formule"),
        choices=[("decouverte", _l("Decouverte (gratuit)")), ("standard", _l("Standard")), ("pro", _l("Pro"))],
        default="decouverte",
    )
    is_demo = BooleanField(_l("Tenant de demonstration"))

    owner_first_name = StringField(_l("Prenom du proprietaire"), validators=[DataRequired(), Length(max=80)])
    owner_last_name = StringField(_l("Nom du proprietaire"), validators=[DataRequired(), Length(max=80)])
    owner_email = StringField(_l("Email du proprietaire"), validators=[DataRequired(), Email()])
    owner_password = PasswordField(_l("Mot de passe initial"), validators=[DataRequired(), Length(min=8)])

    submit = SubmitField(_l("Creer le client"))


class UserForm(FlaskForm):
    first_name = StringField(_l("Prenom"), validators=[DataRequired(), Length(max=80)])
    last_name = StringField(_l("Nom"), validators=[DataRequired(), Length(max=80)])
    email = StringField(_l("Email"), validators=[DataRequired(), Email()])
    role = SelectField(
        _l("Role"),
        choices=[(ROLE_MANAGER, ROLE_LABELS[ROLE_MANAGER]), (ROLE_WORKER, ROLE_LABELS[ROLE_WORKER])],
    )
    farm_id = SelectField(_l("Ferme assignee"), coerce=int, validators=[Optional()])
    password = PasswordField(_l("Mot de passe initial"), validators=[DataRequired(), Length(min=8)])
    submit = SubmitField(_l("Creer l'utilisateur"))


class UserEditForm(FlaskForm):
    """Corrige les informations d'un utilisateur existant (role, ferme
    assignee, coordonnees) - le mot de passe n'est change que si un nouveau
    est saisi, pour ne pas forcer une reinitialisation a chaque correction."""

    first_name = StringField(_l("Prenom"), validators=[DataRequired(), Length(max=80)])
    last_name = StringField(_l("Nom"), validators=[DataRequired(), Length(max=80)])
    email = StringField(_l("Email"), validators=[DataRequired(), Email()])
    role = SelectField(
        _l("Role"),
        choices=[(ROLE_MANAGER, ROLE_LABELS[ROLE_MANAGER]), (ROLE_WORKER, ROLE_LABELS[ROLE_WORKER])],
    )
    farm_id = SelectField(_l("Ferme assignee"), coerce=int, validators=[Optional()])
    password = PasswordField(_l("Nouveau mot de passe (laisser vide pour ne pas changer)"), validators=[Optional(), Length(min=8)])
    submit = SubmitField(_l("Enregistrer"))


# Les 54 pays membres de l'Union Africaine + "Autre" en repli. Chacun est
# associe a sa devise officielle (COUNTRY_CURRENCY) pour la suggestion
# automatique dans /parametres (paragraphe "tous les pays d'Afrique").
COUNTRY_CURRENCY = {
    "Afrique du Sud": "ZAR",
    "Algerie": "DZD",
    "Angola": "AOA",
    "Benin": "XOF",
    "Botswana": "BWP",
    "Burkina Faso": "XOF",
    "Burundi": "BIF",
    "Cameroun": "XAF",
    "Cap-Vert": "CVE",
    "Comores": "KMF",
    "Congo": "XAF",
    "Cote d'Ivoire": "XOF",
    "Djibouti": "DJF",
    "Egypte": "EGP",
    "Erythree": "ERN",
    "Eswatini": "SZL",
    "Ethiopie": "ETB",
    "Gabon": "XAF",
    "Gambie": "GMD",
    "Ghana": "GHS",
    "Guinee": "GNF",
    "Guinee-Bissau": "XOF",
    "Guinee equatoriale": "XAF",
    "Kenya": "KES",
    "Lesotho": "LSL",
    "Liberia": "LRD",
    "Libye": "LYD",
    "Madagascar": "MGA",
    "Malawi": "MWK",
    "Mali": "XOF",
    "Maroc": "MAD",
    "Maurice": "MUR",
    "Mauritanie": "MRU",
    "Mozambique": "MZN",
    "Namibie": "NAD",
    "Niger": "XOF",
    "Nigeria": "NGN",
    "Ouganda": "UGX",
    "RD Congo": "CDF",
    "Republique centrafricaine": "XAF",
    "Rwanda": "RWF",
    "Sao Tome-et-Principe": "STN",
    "Senegal": "XOF",
    "Seychelles": "SCR",
    "Sierra Leone": "SLE",
    "Somalie": "SOS",
    "Soudan": "SDG",
    "Soudan du Sud": "SSP",
    "Tanzanie": "TZS",
    "Tchad": "XAF",
    "Togo": "XOF",
    "Tunisie": "TND",
    "Zambie": "ZMW",
    "Zimbabwe": "ZWL",
}

# Marqueurs d'extraction des traductions : les noms de pays sont stockes
# tels quels (francais) en base, seul leur libelle affiche est traduit.
_COUNTRY_NAME_MARKERS = (
    _l("Afrique du Sud"),
    _l("Algerie"),
    _l("Angola"),
    _l("Benin"),
    _l("Botswana"),
    _l("Burkina Faso"),
    _l("Burundi"),
    _l("Cameroun"),
    _l("Cap-Vert"),
    _l("Comores"),
    _l("Congo"),
    _l("Cote d'Ivoire"),
    _l("Djibouti"),
    _l("Egypte"),
    _l("Erythree"),
    _l("Eswatini"),
    _l("Ethiopie"),
    _l("Gabon"),
    _l("Gambie"),
    _l("Ghana"),
    _l("Guinee"),
    _l("Guinee-Bissau"),
    _l("Guinee equatoriale"),
    _l("Kenya"),
    _l("Lesotho"),
    _l("Liberia"),
    _l("Libye"),
    _l("Madagascar"),
    _l("Malawi"),
    _l("Mali"),
    _l("Maroc"),
    _l("Maurice"),
    _l("Mauritanie"),
    _l("Mozambique"),
    _l("Namibie"),
    _l("Niger"),
    _l("Nigeria"),
    _l("Ouganda"),
    _l("RD Congo"),
    _l("Republique centrafricaine"),
    _l("Rwanda"),
    _l("Sao Tome-et-Principe"),
    _l("Senegal"),
    _l("Seychelles"),
    _l("Sierra Leone"),
    _l("Somalie"),
    _l("Soudan"),
    _l("Soudan du Sud"),
    _l("Tanzanie"),
    _l("Tchad"),
    _l("Togo"),
    _l("Tunisie"),
    _l("Zambie"),
    _l("Zimbabwe"),
)

COUNTRY_CHOICES = [(name, _l(name)) for name in sorted(COUNTRY_CURRENCY)] + [("Autre", _l("Autre"))]


class SettingsForm(FlaskForm):
    # -- General ---------------------------------------------------------
    name = StringField(_l("Nom de l'exploitation"), validators=[DataRequired(), Length(max=150)])
    country = SelectField(_l("Pays"), choices=COUNTRY_CHOICES, validators=[Optional()])
    default_language = SelectField(
        _l("Langue par defaut pour les nouveaux utilisateurs"),
        choices=[("fr", _l("Francais")), ("en", _l("English"))],
        default="fr",
    )
    currency_label = StringField(
        _l("Devise affichee"),
        validators=[DataRequired(), Length(max=10)],
        default="FCFA",
        render_kw={"placeholder": _l("Ex : FCFA")},
    )

    # -- Elevage ---------------------------------------------------------
    default_breed = StringField(
        _l("Souche par defaut pour les nouveaux lots"),
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": _l("Ex : Ross 308")},
    )
    default_cycle_days = IntegerField(
        _l("Duree de cycle standard (jours)"),
        validators=[Optional(), NumberRange(min=1, max=365)],
        render_kw={"placeholder": _l("Ex : 42")},
    )
    fcr_alert_threshold = DecimalField(
        _l("Seuil d'alerte pour l'aliment par poulet"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 2.0")},
    )

    # -- Alertes ---------------------------------------------------------
    mortality_alert_threshold_percent = DecimalField(
        _l("Seuil de mortalite quotidienne qui declenche une alerte (%)"),
        validators=[DataRequired(), NumberRange(min=0, max=100)],
        places=2,
        default=3,
    )
    sanitary_reminder_interval_minutes = IntegerField(
        _l("Frequence du rappel sanitaire (minutes)"),
        validators=[DataRequired(), NumberRange(min=1, max=1440)],
        default=10,
    )
    email_alerts_enabled = BooleanField(
        _l("Activer les alertes par email pour toute l'exploitation"), default=True
    )

    # -- Stock -----------------------------------------------------------
    default_stock_low_threshold = DecimalField(
        _l("Seuil d'alerte stock faible suggere par defaut"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 2")},
    )

    # -- Finance ---------------------------------------------------------
    default_labor_cost_per_day = DecimalField(
        _l("Cout main d'oeuvre par defaut / jour"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": _l("Ex : 2000")},
    )
    default_sale_unit = SelectField(
        _l("Mode de vente par defaut"),
        choices=[("unit", _l("Au sujet (par poulet)")), ("kg", _l("Au kilogramme"))],
        default="unit",
    )

    # -- Securite ---------------------------------------------------------
    max_login_attempts = IntegerField(
        _l("Nombre d'essais avant verrouillage du compte"),
        validators=[DataRequired(), NumberRange(min=1, max=20)],
        default=5,
    )
    login_lockout_minutes = IntegerField(
        _l("Duree de verrouillage apres echecs (minutes)"),
        validators=[DataRequired(), NumberRange(min=1, max=1440)],
        default=15,
    )

    submit = SubmitField(_l("Enregistrer"))


class ProfileForm(FlaskForm):
    first_name = StringField(_l("Prenom"), validators=[DataRequired(), Length(max=80)])
    last_name = StringField(_l("Nom"), validators=[DataRequired(), Length(max=80)])
    email = StringField(_l("Adresse email"), validators=[DataRequired(), Email()])
    avatar = FileField(
        _l("Photo de profil"),
        validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], _l("Format d'image non autorise."))],
    )
    email_notifications_enabled = BooleanField(_l("Recevoir les alertes urgentes par email"))
    submit = SubmitField(_l("Enregistrer"))
