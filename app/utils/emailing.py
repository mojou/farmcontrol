"""Notifications email (paragraphe 3.3)."""
from flask import render_template
from flask_mail import Message

from app.extensions import mail


def _send(subject: str, recipients: list, template_base: str, **context):
    if not recipients:
        return
    msg = Message(subject=subject, recipients=recipients)
    msg.body = render_template(f"{template_base}.txt", **context)
    try:
        msg.html = render_template(f"{template_base}.html", **context)
    except Exception:
        pass
    mail.send(msg)


def send_alert_email(alert, recipients: list):
    """Envoie un email pour une alerte urgente ou importante (paragraphe 3.2)."""
    subject = f"[Farm Control] {alert.title}"
    _send(subject, recipients, "email/alert", alert=alert)


def send_password_reset_email(user, reset_url: str):
    subject = "Farm Control - Reinitialisation de votre mot de passe"
    _send(subject, [user.email], "email/password_reset", user=user, reset_url=reset_url)


def send_welcome_email(user, temporary_password: str = None):
    subject = "Farm Control - Votre compte a ete cree"
    _send(subject, [user.email], "email/welcome", user=user, temporary_password=temporary_password)
