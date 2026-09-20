from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class SignupForm(FlaskForm):
    organization_name = StringField(
        _l("Nom de votre exploitation / entreprise"), validators=[DataRequired(), Length(max=150)]
    )
    first_name = StringField(_l("Prenom"), validators=[DataRequired(), Length(max=80)])
    last_name = StringField(_l("Nom"), validators=[DataRequired(), Length(max=80)])
    email = StringField(_l("Adresse email"), validators=[DataRequired(), Email()])
    password = PasswordField(_l("Mot de passe"), validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField(
        _l("Confirmer le mot de passe"),
        validators=[DataRequired(), EqualTo("password", message=_l("Les mots de passe ne correspondent pas."))],
    )
    accept_terms = BooleanField(
        _l("J'accepte les Conditions Generales d'Utilisation et la Politique de Confidentialite"),
        validators=[DataRequired(message=_l("Vous devez accepter les conditions pour continuer."))],
    )
    submit = SubmitField(_l("Creer mon compte"))


class LoginForm(FlaskForm):
    email = StringField(_l("Adresse email"), validators=[DataRequired(), Email()])
    password = PasswordField(_l("Mot de passe"), validators=[DataRequired()])
    remember_me = BooleanField(_l("Se souvenir de moi"))
    submit = SubmitField(_l("Se connecter"))


class ForgotPasswordForm(FlaskForm):
    email = StringField(_l("Adresse email"), validators=[DataRequired(), Email()])
    submit = SubmitField(_l("Envoyer le lien de reinitialisation"))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l("Nouveau mot de passe"), validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField(
        _l("Confirmer le mot de passe"),
        validators=[DataRequired(), EqualTo("password", message=_l("Les mots de passe ne correspondent pas."))],
    )
    submit = SubmitField(_l("Reinitialiser le mot de passe"))


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(_l("Mot de passe actuel"), validators=[DataRequired()])
    password = PasswordField(_l("Nouveau mot de passe"), validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField(
        _l("Confirmer le nouveau mot de passe"),
        validators=[DataRequired(), EqualTo("password", message=_l("Les mots de passe ne correspondent pas."))],
    )
    submit = SubmitField(_l("Mettre a jour le mot de passe"))
