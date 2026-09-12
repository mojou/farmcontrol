from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class ComposeMessageForm(FlaskForm):
    recipient_id = SelectField("Destinataire", coerce=int, validators=[DataRequired()])
    subject = StringField("Sujet", validators=[DataRequired(), Length(max=200)])
    body = TextAreaField("Message", validators=[DataRequired()])
    submit = SubmitField("Envoyer")


class ReplyMessageForm(FlaskForm):
    body = TextAreaField("Votre reponse", validators=[DataRequired()])
    submit = SubmitField("Repondre")
