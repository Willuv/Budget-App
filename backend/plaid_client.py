import time
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


def _parse_plaid_response(response):
    try:
        payload = response.json()
    except ValueError:
        payload = None

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        message = None
        if isinstance(payload, dict):
            message = payload.get("error_message") or payload.get("error_description") or payload.get("display_message")
        if not message:
            message = response.text or str(exc)
        raise requests.HTTPError(message, response=response) from exc

    return payload


def _get_plaid_error_details(response):
    try:
        payload = response.json()
    except ValueError:
        payload = None

    error_code = None
    message = None
    if isinstance(payload, dict):
        error_code = payload.get("error_code")
        message = payload.get("error_message") or payload.get("error_description") or payload.get("display_message")

    if not message:
        message = response.text

    return payload, error_code, message


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
    payload = _parse_plaid_response(response)
    return payload["link_token"]


def exchange_public_token(public_token: str):
    auth_payload, env = _auth_payload()
    response = requests.post(
        f"{plaid_base_url(env)}/item/public_token/exchange",
        json={**auth_payload, "public_token": public_token},
        timeout=ERROR_TIMEOUT_SECONDS,
    )
    payload = _parse_plaid_response(response)
    return payload["access_token"], payload.get("item_id")


def create_sandbox_public_token(institution_id: str = "ins_109508", products=None):
    auth_payload, env = _auth_payload()
    if env != "sandbox":
        raise ValueError("Sandbox token creation only works in the sandbox environment.")

    body = {
        **auth_payload,
        "institution_id": institution_id,
        "initial_products": products or ["transactions"],
    }
    response = requests.post(
        f"{plaid_base_url(env)}/sandbox/public_token/create",
        json=body,
        timeout=ERROR_TIMEOUT_SECONDS,
    )
    payload = _parse_plaid_response(response)
    return payload["public_token"]


def fetch_latest_transactions(access_token: str, days_back: int = 60):
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
        },
    }
    for attempt in range(3):
        response = requests.post(
            f"{plaid_base_url(env)}/transactions/get",
            json=body,
            timeout=ERROR_TIMEOUT_SECONDS,
        )
        payload, error_code, _ = _get_plaid_error_details(response)
        if error_code == "PRODUCT_NOT_READY" and attempt < 2:
            time.sleep(1.5)
            continue
        payload = _parse_plaid_response(response)
        return payload.get("accounts", []), payload.get("transactions", [])

    return [], []


def fetch_identity(access_token: str):
    auth_payload, env = _auth_payload()
    response = requests.post(
        f"{plaid_base_url(env)}/identity/get",
        json={**auth_payload, "access_token": access_token},
        timeout=ERROR_TIMEOUT_SECONDS,
    )
    payload = _parse_plaid_response(response)

    identity_data = payload.get("identity") or {}
    names = identity_data.get("names") or []
    if not names:
        names = []
        for owner in identity_data.get("owners", []) or []:
            owner_names = owner.get("names") or []
            if owner_names:
                names.extend(owner_names)

    return {
        "name": names[0] if names else None,
        "names": names,
        "email_addresses": identity_data.get("email_addresses") or [],
        "phone_numbers": identity_data.get("phone_numbers") or [],
    }