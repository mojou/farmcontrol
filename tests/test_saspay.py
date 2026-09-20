"""Integration SasPay - toutes les requetes reseau sont simulees (mock) :
la suite automatisee ne doit jamais appeler la vraie API, encore moins avec
une clef "live". Ces tests fixent surtout le format d'enveloppe reel de
l'API ({"success", "data", "code"}) decouvert en testant en direct - une
regression dessus casserait silencieusement tout paiement."""
from unittest.mock import patch

import pytest

from app.utils.saspay import SaspayError, verify_checkout_session, verify_webhook_signature


def _mock_response(status_code, json_data):
    class _Resp:
        def __init__(self):
            self.status_code = status_code
            self.content = b"1"

        def json(self):
            return json_data

    return _Resp()


@pytest.fixture()
def saspay_app(app):
    with app.app_context():
        app.config["SASPAY_ENABLED"] = True
        app.config["SASPAY_SECRET_KEY"] = "sk_test_fake"
        app.config["SASPAY_BASE_URL"] = "https://api.saspay.me/api/v1"
        app.config["SASPAY_CURRENCY"] = "XAF"
        app.config["SASPAY_COUNTRY"] = "CM"
        yield app


def test_init_payment_unwraps_envelope(saspay_app):
    """La reponse reelle enveloppe le contenu dans {"success", "data", "code"} -
    pas le format plat suggere par les exemples de la documentation."""
    from app.utils.saspay import init_payment

    wrapped = {
        "success": True,
        "code": 201,
        "data": {
            "id": "session-123",
            "checkout_url": "https://checkout.saspay.me/abc",
            "status": "PENDING",
            "transaction": None,
        },
    }
    with saspay_app.app_context():
        with patch("app.utils.saspay.requests.post", return_value=_mock_response(201, wrapped)):
            result = init_payment(
                transaction_id="fc-1", amount_xaf=5000, description="Test",
                customer_email="a@example.com", customer_name="A",
                notify_url="https://x/notify", return_url="https://x/retour",
            )
    assert result["payment_url"] == "https://checkout.saspay.me/abc"
    assert result["session_id"] == "session-123"
    assert result["simulated"] is False


def test_init_payment_simulated_when_not_configured(app):
    from app.utils.saspay import init_payment

    with app.app_context():
        app.config["SASPAY_ENABLED"] = False
        result = init_payment(
            transaction_id="fc-1", amount_xaf=5000, description="Test",
            customer_email="a@example.com", customer_name="A",
            notify_url="https://x/notify", return_url="https://x/retour",
        )
    assert result["simulated"] is True
    assert result["payment_url"] is None


def test_verify_checkout_session_pending_without_transaction(saspay_app):
    session_response = {
        "success": True, "code": 200,
        "data": {"id": "session-123", "status": "PENDING", "transaction": None},
    }
    with saspay_app.app_context():
        with patch("app.utils.saspay.requests.get", return_value=_mock_response(200, session_response)):
            result = verify_checkout_session("session-123")
    assert result["status"] == "PENDING"


def test_verify_checkout_session_cancelled_is_failed(saspay_app):
    """Une session annulee/expiree n'aura jamais de transaction : sans ce
    cas particulier, elle resterait PENDING pour toujours a chaque relance."""
    session_response = {
        "success": True, "code": 200,
        "data": {"id": "session-123", "status": "CANCELLED", "transaction": None},
    }
    with saspay_app.app_context():
        with patch("app.utils.saspay.requests.get", return_value=_mock_response(200, session_response)):
            result = verify_checkout_session("session-123")
    assert result["status"] == "FAILED"


def test_verify_checkout_session_success_follows_transaction(saspay_app):
    session_response = {
        "success": True, "code": 200,
        "data": {"id": "session-123", "status": "PENDING", "transaction": {"id": "txn-456"}},
    }
    payment_response = {
        "success": True, "code": 200,
        "data": {"id": "txn-456", "status": "SUCCESS"},
    }
    with saspay_app.app_context():
        with patch("app.utils.saspay.requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(200, session_response),
                _mock_response(200, payment_response),
            ]
            result = verify_checkout_session("session-123")
    assert result["status"] == "SUCCESS"
    # Doit bien avoir suivi jusqu'au point de verification dedie, pas juste
    # lu le statut de la session.
    assert mock_get.call_count == 2
    assert "txn-456" in mock_get.call_args_list[1][0][0]


def test_verify_payment_error_raises(saspay_app):
    from app.utils.saspay import verify_payment

    error_response = {"message": "Transaction introuvable.", "code": "not_found"}
    with saspay_app.app_context():
        with patch("app.utils.saspay.requests.get", return_value=_mock_response(404, error_response)):
            with pytest.raises(SaspayError, match="introuvable"):
                verify_payment("unknown-id")


def test_webhook_signature_valid_and_invalid(saspay_app):
    import hashlib
    import hmac
    import time

    with saspay_app.app_context():
        saspay_app.config["SASPAY_WEBHOOK_SECRET"] = "whsec_test"
        body = b'{"event":"transaction.success"}'
        ts = str(int(time.time()))
        good_sig = hmac.new(b"whsec_test", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()

        assert verify_webhook_signature(body, good_sig, ts) is True
        assert verify_webhook_signature(body, "wrong", ts) is False
        assert verify_webhook_signature(body, good_sig, str(int(time.time()) - 1000)) is False
        assert verify_webhook_signature(body, "", "") is False
