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


def cache_transactions(transaction_list):
    conn = get_db_connection()
    cursor = conn.cursor()
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
                transaction.get("amount"),
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
