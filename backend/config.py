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
}


def load_settings():
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "client_id": str(data.get("client_id", "")).strip(),
                    "secret": str(data.get("secret", "")).strip(),
                    "env": str(data.get("env", "sandbox")).strip() or "sandbox",
                }
        except (json.JSONDecodeError, OSError):
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(client_id: str, secret: str, env: str = "sandbox"):
    payload = {
        "client_id": client_id.strip(),
        "secret": secret.strip(),
        "env": env.strip() or "sandbox",
    }
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    return payload


def plaid_base_url(env: str) -> str:
    return PLAID_ENVIRONMENTS.get(env, PLAID_ENVIRONMENTS["sandbox"])
