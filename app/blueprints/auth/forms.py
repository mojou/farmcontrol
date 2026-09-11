from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class SignupForm(FlaskForm):
    organization_name = StringField(
        "Nom de votre exploitation / entreprise", validators=[DataRequired(), Length(max=150)]
    )
    first_name = StringField("Prenom", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Nom", validators=[DataRequired(), Length(max=80)])
    email = StringField("Adresse email", validators=[DataRequired(), Email()])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField(
        "Confirmer le mot de passe",
        validators=[DataRequired(), EqualTo("password", message="Les mots de passe ne correspondent pas.")],
    )
    submit = SubmitField("Creer mon compte")


class LoginForm(FlaskForm):
    email = StringField("Adresse email", validators=[DataRequired(), Email()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])
    remember_me = BooleanField("Se souvenir de moi")
    submit = SubmitField("Se connecter")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Adresse email", validators=[DataRequired(), Email()])
    submit = SubmitField("Envoyer le lien de reinitialisation")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Nouveau mot de passe", validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField(
        "Confirmer le mot de passe",
        validators=[DataRequired(), EqualTo("password", message="Les mots de passe ne correspondent pas.")],
    )
    submit = SubmitField("Reinitialiser le mot de passe")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Mot de passe actuel", validators=[DataRequired()])
    password = PasswordField("Nouveau mot de passe", validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[DataRequired(), EqualTo("password", message="Les mots de passe ne correspondent pas.")],
    )
    submit = SubmitField("Mettre a jour le mot de passe")
