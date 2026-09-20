from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class ComposeMessageForm(FlaskForm):
    recipient_id = SelectField(_l("Destinataire"), coerce=int, validators=[DataRequired()])
    subject = StringField(_l("Sujet"), validators=[DataRequired(), Length(max=200)])
    body = TextAreaField(_l("Message"), validators=[DataRequired()])
    submit = SubmitField(_l("Envoyer"))


class ReplyMessageForm(FlaskForm):
    body = TextAreaField(_l("Votre reponse"), validators=[DataRequired()])
    submit = SubmitField(_l("Repondre"))
