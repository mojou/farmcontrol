"""Client Brevo (ex-Sendinblue) pour l'envoi d'emails transactionnels via
l'API HTTP plutot qu'une connexion SMTP directe (plus fiable sur un
hebergeur gratuit ou le port SMTP 587 peut etre bride ou instable).

Documentation : https://developers.brevo.com/reference/sendtransacemail
"""
import requests
from flask import current_app

BREVO_TIMEOUT_SECONDS = 15
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoError(Exception):
    pass


def is_configured() -> bool:
    return bool(current_app.config.get("BREVO_API_KEY"))


def send_email(*, to_email: str, subject: str, html_content: str, text_content: str = None, to_name: str = None) -> dict:
    if not is_configured():
        raise BrevoError("Brevo n'est pas configure (BREVO_API_KEY manquant).")

    payload = {
        "sender": {
            "email": current_app.config["MAIL_DEFAULT_SENDER"],
            "name": "Farm Control",
        },
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    if text_content:
        payload["textContent"] = text_content

    try:
        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={
                "api-key": current_app.config["BREVO_API_KEY"],
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=BREVO_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = exc.response.text if getattr(exc, "response", None) is not None else str(exc)
        raise BrevoError(f"Erreur envoi email Brevo : {detail}") from exc

    return response.json()
