from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

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


COUNTRY_CHOICES = [
    ("Cameroun", "Cameroun"),
    ("Senegal", "Senegal"),
    ("Cote d'Ivoire", "Cote d'Ivoire"),
    ("Mali", "Mali"),
    ("Burkina Faso", "Burkina Faso"),
    ("Niger", "Niger"),
    ("Tchad", "Tchad"),
    ("Benin", "Benin"),
    ("Togo", "Togo"),
    ("Gabon", "Gabon"),
    ("Congo", "Congo"),
    ("Republique centrafricaine", "Republique centrafricaine"),
    ("Guinee equatoriale", "Guinee equatoriale"),
    ("RD Congo", "RD Congo"),
    ("Autre", "Autre"),
]


class SettingsForm(FlaskForm):
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
