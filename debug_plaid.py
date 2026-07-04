from backend.plaid_client import create_sandbox_public_token, exchange_public_token, fetch_latest_transactions
from backend.config import load_settings
import traceback

settings = load_settings()
print('settings env', settings)
try:
    public_token = create_sandbox_public_token()
    print('public_token', public_token)
    access_token, item_id = exchange_public_token(public_token)
    print('access_token', access_token[:10] + '...', 'item_id', item_id)
    accounts, txns = fetch_latest_transactions(access_token)
    print('accounts', len(accounts), 'txns', len(txns))
except Exception:
    traceback.print_exc()
