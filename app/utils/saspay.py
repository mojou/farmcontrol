"""Client SasPay (paiement Mobile Money/carte, Afrique de l'Ouest et
Centrale). Documentation : https://docs.saspay.me

Si SASPAY_ENABLED est faux (clef secrete non renseignee), les fonctions
d'initialisation renvoient un resultat "simule" clairement marque comme
tel : cela permet de demontrer le parcours d'abonnement de bout en bout
avant meme d'avoir une clef active.

Flux de correlation : une session de paiement (checkout session) ne
contient pas directement de champ de reference que l'on controle - on
integre donc son propre identifiant de transaction interne dans return_url
(comme pour CinetPay) plutot que de compter sur SasPay pour le renvoyer.
Le webhook sert uniquement de declencheur pour revalider tout ce qui est
en attente aupres de l'API (jamais de confiance dans le contenu du webhook
seul), suivant leur propre recommandation ("toujours l'etat reel cote
gateway, jamais confiance dans un statut memorise").
"""
import hashlib
import hmac
import time

import requests
from flask import current_app

SASPAY_TIMEOUT_SECONDS = 15
WEBHOOK_MAX_CLOCK_DRIFT_SECONDS = 300


class SaspayError(Exception):
    pass


def is_configured() -> bool:
    return bool(current_app.config.get("SASPAY_ENABLED"))


def _headers() -> dict:
    return {"Authorization": f"Bearer {current_app.config['SASPAY_SECRET_KEY']}"}


def _unwrap(data: dict) -> dict:
    """Toutes les reponses SasPay reussies enveloppent le contenu utile dans
    {"success": true, "data": {...}, "code": ...} - les erreurs, elles, sont
    directement {"message": ..., "code": ...} sans cette enveloppe."""
    if isinstance(data, dict) and data.get("success") and isinstance(data.get("data"), dict):
        return data["data"]
    return data


def init_payment(*, transaction_id: str, amount_xaf: int, description: str, customer_email: str,
                  customer_name: str, notify_url: str, return_url: str) -> dict:
    """Cree une session de paiement (checkout session).

    Retourne un dict {"simulated": bool, "payment_url": str|None,
    "session_id": str|None, "raw": dict}. Si SasPay n'est pas configure,
    retourne un resultat simule (aucun appel reseau).
    """
    if not is_configured():
        return {"simulated": True, "payment_url": None, "session_id": None, "raw": {}}

    payload = {
        "amount": f"{amount_xaf:.2f}",
        "currency": current_app.config["SASPAY_CURRENCY"],
        "country": current_app.config["SASPAY_COUNTRY"],
        "description": description[:255],
        "customer_email": customer_email,
        "customer_name": customer_name or "Client",
        "return_url": return_url,
        "metadata": {"transaction_id": transaction_id},
    }

    try:
        response = requests.post(
            f"{current_app.config['SASPAY_BASE_URL']}/checkout-sessions/",
            json=payload,
            headers=_headers(),
            timeout=SASPAY_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise SaspayError(f"Erreur reseau SasPay : {exc}") from exc

    data = response.json() if response.content else {}
    if response.status_code != 201:
        raise SaspayError(data.get("message") or data.get("detail") or "Echec de creation de la session SasPay.")

    session = _unwrap(data)
    return {
        "simulated": False,
        "payment_url": session.get("checkout_url"),
        "session_id": session.get("id"),
        "raw": session,
    }


def get_checkout_session(session_id: str) -> dict:
    """Recupere l'etat actuel d'une session de paiement."""
    if not is_configured():
        raise SaspayError("SasPay n'est pas configure.")

    try:
        response = requests.get(
            f"{current_app.config['SASPAY_BASE_URL']}/checkout-sessions/{session_id}/",
            headers=_headers(),
            timeout=SASPAY_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise SaspayError(f"Erreur reseau SasPay : {exc}") from exc

    data = response.json() if response.content else {}
    if response.status_code != 200:
        raise SaspayError(data.get("message") or data.get("detail") or "Session SasPay introuvable.")
    return _unwrap(data)


def verify_payment(payment_id: str) -> dict:
    """Verifie le statut reel d'un paiement (transaction) aupres de SasPay.

    Retourne {"status": "SUCCESS"|"FAILED"|"PENDING", "raw": dict}.
    """
    if not is_configured():
        raise SaspayError("SasPay n'est pas configure.")

    try:
        response = requests.get(
            f"{current_app.config['SASPAY_BASE_URL']}/payments/{payment_id}/verify/",
            headers=_headers(),
            timeout=SASPAY_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise SaspayError(f"Erreur reseau SasPay : {exc}") from exc

    data = response.json() if response.content else {}
    if response.status_code != 200:
        raise SaspayError(data.get("message") or data.get("detail") or "Paiement SasPay introuvable.")

    transaction = _unwrap(data)
    return {"status": transaction.get("status"), "raw": transaction}


def verify_checkout_session(session_id: str) -> dict:
    """Resout une session de paiement jusqu'a son statut de paiement final.

    Suit le lien session -> transaction puis revalide ce dernier aupres du
    point de verification dedie (jamais de confiance dans le seul statut de
    la session). Retourne {"status": "PENDING"|"SUCCESS"|"FAILED", "raw": dict}.
    """
    session = get_checkout_session(session_id)
    transaction = session.get("transaction")
    if not transaction:
        # Une session annulee ou expiree ne recevra jamais de transaction :
        # sans ca, elle resterait "PENDING" indefiniment a chaque relance.
        if session.get("status") in ("CANCELLED", "EXPIRED"):
            return {"status": "FAILED", "raw": session}
        return {"status": "PENDING", "raw": session}

    transaction_id = transaction.get("id") if isinstance(transaction, dict) else transaction
    return verify_payment(transaction_id)


def verify_webhook_signature(raw_body: bytes, signature: str, timestamp: str) -> bool:
    """Verifie la signature HMAC-SHA256 d'un webhook (voir docs.saspay.me/
    api-reference/webhooks). Rejette aussi tout message trop vieux (rejeu)."""
    secret = current_app.config.get("SASPAY_WEBHOOK_SECRET")
    if not secret or not signature or not timestamp:
        return False

    try:
        if abs(time.time() - float(timestamp)) > WEBHOOK_MAX_CLOCK_DRIFT_SECONDS:
            return False
    except ValueError:
        return False

    signed_payload = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
