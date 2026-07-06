import sqlite3
from pathlib import Path
from backend.config import DB_FILE


def get_db_connection():
    connection = sqlite3.connect(str(DB_FILE), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plaid_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            access_token TEXT NOT NULL,
            item_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            name TEXT,
            mask TEXT,
            type TEXT,
            subtype TEXT,
            current_balance REAL,
            available_balance REAL,
            last_updated TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            account_id TEXT,
            name TEXT,
            amount REAL,
            date TEXT,
            category TEXT,
            city TEXT,
            merchant_name TEXT,
            pending INTEGER DEFAULT 0,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


def save_access_token(access_token: str, item_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM plaid_tokens")
    cursor.execute(
        "INSERT INTO plaid_tokens (access_token, item_id) VALUES (?, ?)",
        (access_token, item_id),
    )
    conn.commit()
    conn.close()


def get_access_token():
    conn = get_db_connection()
    row = conn.execute(
        "SELECT access_token FROM plaid_tokens ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["access_token"] if row else None


def cache_accounts(account_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts")
    for account in account_list:
        cursor.execute(
            """
            INSERT INTO accounts (
                account_id, name, mask, type, subtype, current_balance, available_balance, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                name=excluded.name,
                mask=excluded.mask,
                type=excluded.type,
                subtype=excluded.subtype,
                current_balance=excluded.current_balance,
                available_balance=excluded.available_balance,
                last_updated=excluded.last_updated
            """,
            (
                account.get("account_id"),
                account.get("name"),
                account.get("mask"),
                account.get("type"),
                account.get("subtype"),
                account.get("balances", {}).get("current"),
                account.get("balances", {}).get("available"),
                account.get("balances", {}).get("as_of"),
            ),
        )
    conn.commit()
    conn.close()


def normalize_transaction_amount(amount):
    try:
        return -float(amount or 0)
    except (TypeError, ValueError):
        return 0.0


def cache_transactions(transaction_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions")
    for transaction in transaction_list:
        cursor.execute(
            """
            INSERT INTO transactions (
                transaction_id, account_id, name, amount, date, category, city, merchant_name, pending
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(transaction_id) DO UPDATE SET
                account_id=excluded.account_id,
                name=excluded.name,
                amount=excluded.amount,
                date=excluded.date,
                category=excluded.category,
                city=excluded.city,
                merchant_name=excluded.merchant_name,
                pending=excluded.pending
            """,
            (
                transaction.get("transaction_id"),
                transaction.get("account_id"),
                transaction.get("name"),
                normalize_transaction_amount(transaction.get("amount")),
                transaction.get("date"),
                ", ".join(transaction.get("category", [])[:2]) if transaction.get("category") else "",
                transaction.get("location", {}).get("city"),
                transaction.get("merchant_name"),
                int(transaction.get("pending", False)),
            ),
        )
    conn.commit()
    conn.close()


def get_cached_transactions(limit=50):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY date DESC, imported_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_account_summary():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM accounts ORDER BY name ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_budget_suggestions():
    transactions = get_cached_transactions(200)
    payroll_total = 0.0
    category_totals = {}

    for transaction in transactions:
        amount = float(transaction.get("amount") or 0)
        name = (transaction.get("name") or "").strip().lower()
        category = (transaction.get("category") or "").strip()

        if amount > 0 and any(keyword in name for keyword in ["payroll", "salary", "paycheck", "direct deposit", "deposit"]):
            payroll_total += amount
            continue

        if amount < 0:
            category_key = category or "Other"
            category_totals[category_key] = category_totals.get(category_key, 0.0) + abs(amount)

    categories = []
    for name, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)[:6]:
        categories.append({"name": name, "amount": round(amount, 2)})

    if not categories:
        categories = [
            {"name": "Rent", "amount": 0},
            {"name": "Food", "amount": 0},
            {"name": "Insurance", "amount": 0},
            {"name": "Utilities", "amount": 0},
            {"name": "Transportation", "amount": 0},
        ]

    return {"income": round(payroll_total, 2), "categories": categories}


def get_transactions_by_month(year: int, month: int):
    """Fetches transactions strictly for a specific calendar month."""
    conn = get_db_connection()
    # Format as YYYY-MM for SQL string matching
    month_str = f"{year:04d}-{month:02d}"
    
    rows = conn.execute(
        "SELECT * FROM transactions WHERE strftime('%Y-%m', date) = ? ORDER BY date DESC, imported_at DESC",
        (month_str,)
    ).fetchall()
    
    conn.close()
    return [dict(row) for row in rows]