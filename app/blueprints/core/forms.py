from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DecimalField, IntegerField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from app.models.core import ROLE_LABELS, ROLE_MANAGER, ROLE_WORKER


class TenantForm(FlaskForm):
    name = StringField("Nom de l'exploitation / client", validators=[DataRequired(), Length(max=150)])
    slug = StringField("Identifiant (slug)", validators=[DataRequired(), Length(max=80)])
    plan = SelectField(
        "Formule",
        choices=[("decouverte", "Decouverte (gratuit)"), ("standard", "Standard"), ("pro", "Pro")],
        default="decouverte",
    )
    is_demo = BooleanField("Tenant de demonstration")

    owner_first_name = StringField("Prenom du proprietaire", validators=[DataRequired(), Length(max=80)])
    owner_last_name = StringField("Nom du proprietaire", validators=[DataRequired(), Length(max=80)])
    owner_email = StringField("Email du proprietaire", validators=[DataRequired(), Email()])
    owner_password = PasswordField("Mot de passe initial", validators=[DataRequired(), Length(min=8)])

    submit = SubmitField("Creer le client")


class UserForm(FlaskForm):
    first_name = StringField("Prenom", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Nom", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    role = SelectField(
        "Role",
        choices=[(ROLE_MANAGER, ROLE_LABELS[ROLE_MANAGER]), (ROLE_WORKER, ROLE_LABELS[ROLE_WORKER])],
    )
    farm_id = SelectField("Ferme assignee", coerce=int, validators=[Optional()])
    password = PasswordField("Mot de passe initial", validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Creer l'utilisateur")


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

COUNTRY_CHOICES = [(name, name) for name in sorted(COUNTRY_CURRENCY)] + [("Autre", "Autre")]


class SettingsForm(FlaskForm):
    # -- General ---------------------------------------------------------
    name = StringField(_l("Nom de l'exploitation"), validators=[DataRequired(), Length(max=150)])
    country = SelectField(_l("Pays"), choices=COUNTRY_CHOICES, validators=[Optional()])
    default_language = SelectField(
        _l("Langue par defaut pour les nouveaux utilisateurs"),
        choices=[("fr", "Francais"), ("en", "English")],
        default="fr",
    )
    currency_label = StringField(
        _l("Devise affichee"),
        validators=[DataRequired(), Length(max=10)],
        default="FCFA",
        render_kw={"placeholder": "Ex : FCFA"},
    )

    # -- Elevage ---------------------------------------------------------
    default_breed = StringField(
        _l("Souche par defaut pour les nouveaux lots"),
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Ex : Ross 308"},
    )
    default_cycle_days = IntegerField(
        _l("Duree de cycle standard (jours)"),
        validators=[Optional(), NumberRange(min=1, max=365)],
        render_kw={"placeholder": "Ex : 42"},
    )
    fcr_alert_threshold = DecimalField(
        _l("Seuil d'alerte pour l'aliment par poulet"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 2.0"},
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
        render_kw={"placeholder": "Ex : 2"},
    )

    # -- Finance ---------------------------------------------------------
    default_labor_cost_per_day = DecimalField(
        _l("Cout main d'oeuvre par defaut / jour"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        render_kw={"placeholder": "Ex : 2000"},
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
    first_name = StringField("Prenom", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Nom", validators=[DataRequired(), Length(max=80)])
    email = StringField("Adresse email", validators=[DataRequired(), Email()])
    avatar = FileField(
        "Photo de profil",
        validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Format d'image non autorise.")],
    )
    email_notifications_enabled = BooleanField("Recevoir les alertes urgentes par email")
    submit = SubmitField("Enregistrer")
