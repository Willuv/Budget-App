import requests
from datetime import date, timedelta
from backend.config import load_settings, plaid_base_url

ERROR_TIMEOUT_SECONDS = 30


def _auth_payload():
    settings = load_settings()
    if not settings["client_id"] or not settings["secret"]:
        raise ValueError("Plaid credentials are not configured.")
    return {
        "client_id": settings["client_id"],
        "secret": settings["secret"],
    }, settings["env"]


def create_link_token():
    auth_payload, env = _auth_payload()
    body = {
        "client_name": "Spending Tracker",
        "user": {"client_user_id": "local_user"},
        "products": ["transactions"],
        "country_codes": ["US"],
        "language": "en",
        "webhook": "",
    }
    response = requests.post(
        f"{plaid_base_url(env)}/link/token/create",
        json={**auth_payload, **body},
        timeout=ERROR_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["link_token"]


def exchange_public_token(public_token: str):
    auth_payload, env = _auth_payload()
    response = requests.post(
        f"{plaid_base_url(env)}/item/public_token/exchange",
        json={**auth_payload, "public_token": public_token},
        timeout=ERROR_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["access_token"], payload.get("item_id")


def fetch_latest_transactions(access_token: str, days_back: int = 30):
    auth_payload, env = _auth_payload()
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    end_date = date.today().isoformat()

    body = {
        **auth_payload,
        "access_token": access_token,
        "start_date": start_date,
        "end_date": end_date,
        "options": {
            "include_personal_finance_category": True,
            "include_legacy_transactions": False,
        },
    }
    response = requests.post(
        f"{plaid_base_url(env)}/transactions/get",
        json=body,
        timeout=ERROR_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("accounts", []), payload.get("transactions", [])
