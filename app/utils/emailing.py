"""Notifications email (paragraphe 3.3)."""
from flask import render_template
from flask_mail import Message

from app.extensions import mail
from app.utils import brevo


def _send(subject: str, recipients: list, template_base: str, **context):
    if not recipients:
        return

    text_body = render_template(f"{template_base}.txt", **context)
    try:
        html_body = render_template(f"{template_base}.html", **context)
    except Exception:
        html_body = None

    if brevo.is_configured():
        # Chemin privilegie en production : API HTTP Brevo, plus fiable
        # qu'une connexion SMTP sortante sur un hebergeur gratuit.
        for recipient in recipients:
            brevo.send_email(
                to_email=recipient,
                subject=subject,
                html_content=html_body or f"<pre>{text_body}</pre>",
                text_content=text_body,
            )
        return

    # Repli SMTP classique (developpement local, ou tant que Brevo n'est
    # pas configure) - MAIL_SUPPRESS_SEND=True rend ceci un no-op.
    msg = Message(subject=subject, recipients=recipients)
    msg.body = text_body
    if html_body:
        msg.html = html_body
    mail.send(msg)


def send_alert_email(alert, recipients: list):
    """Envoie un email pour une alerte urgente ou importante (paragraphe 3.2)."""
    subject = f"[Farm Control] {alert.title}"
    _send(subject, recipients, "email/alert", alert=alert)


def send_password_reset_email(user, reset_url: str):
    subject = "Farm Control - Reinitialisation de votre mot de passe"
    _send(subject, [user.email], "email/password_reset", user=user, reset_url=reset_url)


def send_welcome_email(user, temporary_password: str = None, verify_url: str = None):
    subject = "Farm Control - Votre compte a ete cree"
    _send(
        subject, [user.email], "email/welcome",
        user=user, temporary_password=temporary_password, verify_url=verify_url,
    )


def send_email_verification_email(user, verify_url: str):
    """Renvoi independant du mail de bienvenue (voir auth.resend_verification_email)."""
    subject = "Farm Control - Confirmez votre adresse email"
    _send(subject, [user.email], "email/verify_email", user=user, verify_url=verify_url)
