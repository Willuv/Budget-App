import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "settings.json"
DB_FILE = ROOT / "spending_tracker.db"

PLAID_ENVIRONMENTS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}

DEFAULT_SETTINGS = {
    "client_id": "",
    "secret": "",
    "env": "sandbox",
    "budget": {"income": 0, "categories": []},
    "total_saved": 0.0,
}


def _normalize_budget_payload(payload):
    budget = payload.get("budget") if isinstance(payload.get("budget"), dict) else {}
    categories = []
    raw_categories = budget.get("categories", []) if isinstance(budget.get("categories"), list) else []
    for item in raw_categories:
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

    return {"income": income, "categories": categories}


def load_settings():
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "client_id": str(data.get("client_id", "")).strip(),
                    "secret": str(data.get("secret", "")).strip(),
                    "env": str(data.get("env", "sandbox")).strip() or "sandbox",
                    "budget": _normalize_budget_payload(data),
                    "total_saved": float(data.get("total_saved", 0.0)),
                }
        except (json.JSONDecodeError, OSError):
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(client_id: str, secret: str, env: str = "sandbox", budget=None, total_saved=None):
    existing = load_settings()
    payload = {
        "client_id": client_id.strip(),
        "secret": secret.strip(),
        "env": env.strip() or "sandbox",
        "budget": budget if budget is not None else existing.get("budget", DEFAULT_SETTINGS["budget"]),
        "total_saved": total_saved if total_saved is not None else existing.get("total_saved", 0.0),
    }
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    return payload


def plaid_base_url(env: str) -> str:
    return PLAID_ENVIRONMENTS.get(env, PLAID_ENVIRONMENTS["sandbox"])