"""Client CinetPay (paiement Mobile Money MTN/Orange + carte, zone CEMAC).

Documentation : https://docs.cinetpay.com/api/1.0-fr/checkout/initialisation

Si CINETPAY_ENABLED est faux (identifiants marchand non renseignes), les
fonctions d'initialisation renvoient un resultat "simule" clairement marque
comme tel : cela permet de demontrer le parcours d'abonnement de bout en
bout avant meme d'avoir active un compte marchand reel.
"""
import requests
from flask import current_app

CINETPAY_TIMEOUT_SECONDS = 15


class CinetPayError(Exception):
    pass


def is_configured() -> bool:
    return bool(current_app.config.get("CINETPAY_ENABLED"))


def init_payment(*, transaction_id: str, amount_xaf: int, description: str, customer_email: str,
                  customer_name: str, notify_url: str, return_url: str) -> dict:
    """Initie une transaction de paiement.

    Retourne un dict {"simulated": bool, "payment_url": str|None, "raw": dict}.
    Si CinetPay n'est pas configure, retourne un resultat simule (aucun appel
    reseau) plutot que de lever une exception : la demonstration du parcours
    d'abonnement reste possible avant la mise en production du paiement.
    """
    if not is_configured():
        return {"simulated": True, "payment_url": None, "raw": {}}

    payload = {
        "apikey": current_app.config["CINETPAY_API_KEY"],
        "site_id": current_app.config["CINETPAY_SITE_ID"],
        "transaction_id": transaction_id,
        "amount": amount_xaf,
        "currency": current_app.config["CINETPAY_CURRENCY"],
        "description": description[:255],
        "customer_email": customer_email,
        "customer_name": customer_name or "Client",
        "notify_url": notify_url,
        "return_url": return_url,
        "channels": "ALL",
    }

    try:
        response = requests.post(
            f"{current_app.config['CINETPAY_BASE_URL']}/payment",
            json=payload,
            timeout=CINETPAY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise CinetPayError(f"Erreur reseau CinetPay : {exc}") from exc

    if str(data.get("code")) != "201":
        raise CinetPayError(data.get("message", "Echec de l'initialisation du paiement CinetPay."))

    return {
        "simulated": False,
        "payment_url": data.get("data", {}).get("payment_url"),
        "payment_token": data.get("data", {}).get("payment_token"),
        "raw": data,
    }


def verify_payment(transaction_id: str) -> dict:
    """Verifie le statut reel d'une transaction aupres de CinetPay.

    Retourne {"status": "ACCEPTED"|"REFUSED"|..., "payment_method": str|None, "raw": dict}.
    A appeler depuis le webhook de notification ET/OU la page de retour :
    ne jamais faire confiance aux seuls parametres d'URL renvoyes par le
    navigateur pour valider un paiement.
    """
    if not is_configured():
        raise CinetPayError("CinetPay n'est pas configure.")

    payload = {
        "apikey": current_app.config["CINETPAY_API_KEY"],
        "site_id": current_app.config["CINETPAY_SITE_ID"],
        "transaction_id": transaction_id,
    }
    try:
        response = requests.post(
            f"{current_app.config['CINETPAY_BASE_URL']}/payment/check",
            json=payload,
            timeout=CINETPAY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise CinetPayError(f"Erreur reseau CinetPay : {exc}") from exc

    result = data.get("data", {})
    return {
        "status": result.get("status"),
        "payment_method": result.get("payment_method"),
        "raw": data,
    }
