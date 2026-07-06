import requests
from datetime import date
from flask import Blueprint, jsonify, render_template, request, send_from_directory
from backend.config import load_settings, save_settings
from backend.database import (
    cache_accounts,
    cache_transactions,
    get_access_token,
    get_account_summary,
    get_cached_transactions,
    get_transactions_by_month,
    save_access_token,
)
from backend.plaid_client import (
    create_link_token,
    create_sandbox_public_token,
    exchange_public_token,
    fetch_identity,
    fetch_latest_transactions,
)

api_bp = Blueprint("api", __name__)


def error_response(message: str, status_code: int = 400):
    return jsonify({"status": "error", "message": message}), status_code


def sync_plaid_data(access_token: str):
    accounts, transactions = fetch_latest_transactions(access_token)
    identity = fetch_identity(access_token)
    cache_accounts(accounts)
    cache_transactions(transactions)
    return accounts, transactions, identity


@api_bp.route("/")
def index():
    settings = load_settings()
    has_keys = bool(settings["client_id"] and settings["secret"])
    return render_template("index.html", has_keys=has_keys)


@api_bp.route("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.svg", mimetype="image/svg+xml")


@api_bp.route("/api/settings", methods=["GET", "POST"])
def settings_route():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        client_id = data.get("client_id", "")
        secret = data.get("secret", "")
        env = data.get("env", "sandbox")
        saved = save_settings(client_id, secret, env)
        return jsonify({"status": "success", "settings": saved})

    return jsonify({"status": "success", "settings": load_settings()})


@api_bp.route("/api/budget", methods=["GET", "POST"])
def budget_route():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        budget = data.get("budget") or data
        categories = []
        for item in budget.get("categories", []) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip() or "Category"
            try:
                amount = float(item.get("amount", 0) or 0)
            except (TypeError, ValueError):
                amount = 0.0
            categories.append({"name": name, "amount": amount})

        try:
            income = float(budget.get("income", 0) or 0)
        except (TypeError, ValueError):
            income = 0.0

        settings = load_settings()
        saved = save_settings(settings["client_id"], settings["secret"], settings["env"], {"income": income, "categories": categories})
        return jsonify({"status": "success", "budget": saved["budget"]})

    settings = load_settings()
    budget = settings.get("budget") or {"income": 0, "categories": []}
    if not budget.get("categories") and not budget.get("income"):
        from backend.database import get_budget_suggestions
        budget = get_budget_suggestions()
    return jsonify({"status": "success", "budget": budget})


@api_bp.route("/api/plaid-link-token", methods=["GET"])
def plaid_link_token():
    try:
        link_token = create_link_token()
        return jsonify({"status": "success", "link_token": link_token})
    except ValueError as exc:
        return error_response(str(exc), 422)
    except requests.RequestException as exc:
        return error_response("Unable to connect to Plaid. Check your internet connection and credentials.", 502)


@api_bp.route("/api/plaid/sandbox-test", methods=["POST"])
def plaid_sandbox_test():
    try:
        public_token = create_sandbox_public_token()
        access_token, item_id = exchange_public_token(public_token)
        save_access_token(access_token, item_id)
        accounts, transactions, identity = sync_plaid_data(access_token)
        return jsonify({"status": "success", "accounts": accounts, "transactions": transactions, "identity": identity})
    except ValueError as exc:
        return error_response(str(exc), 422)
    except requests.RequestException as exc:
        return error_response(f"Failed to create a Plaid sandbox token: {str(exc)}", 502)


@api_bp.route("/api/plaid/exchange-public-token", methods=["POST"])
def plaid_exchange_public_token():
    data = request.get_json(silent=True) or {}
    public_token = data.get("public_token")
    if not public_token:
        return error_response("Missing Plaid public_token.", 400)

    try:
        access_token, item_id = exchange_public_token(public_token)
        save_access_token(access_token, item_id)
        accounts, transactions, identity = sync_plaid_data(access_token)
        return jsonify({"status": "success", "accounts": accounts, "transactions": transactions, "identity": identity})
    except requests.RequestException:
        return error_response("Failed to exchange the public token with Plaid.", 502)
    except ValueError as exc:
        return error_response(str(exc), 422)


@api_bp.route("/api/refresh-transactions", methods=["POST"])
def refresh_transactions():
    access_token = get_access_token()
    if not access_token:
        return error_response("No connected Plaid account found. Please connect first.", 404)

    try:
        accounts, transactions, identity = sync_plaid_data(access_token)
        return jsonify({"status": "success", "accounts": accounts, "transactions": transactions, "identity": identity})
    except requests.RequestException:
        return error_response("Unable to refresh transactions. Please check the internet connection.", 502)
    except ValueError as exc:
        return error_response(str(exc), 422)


@api_bp.route("/api/transactions", methods=["GET"])
def transactions_route():
    access_token = get_access_token()
    identity = {"name": None, "names": [], "email_addresses": [], "phone_numbers": []}
    
    if access_token:
        try:
            identity = fetch_identity(access_token)
        except requests.RequestException:
            pass

    # Default to current calendar month
    today = date.today()
    year = request.args.get("year", default=today.year, type=int)
    month = request.args.get("month", default=today.month, type=int)

    # Fetch filtered transactions
    transactions = get_transactions_by_month(year, month)

    return jsonify(
        {
            "status": "success",
            "linked": bool(access_token),
            "transactions": transactions,
            "accounts": get_account_summary(),
            "identity": identity,
        }
    )