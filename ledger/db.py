# ledger/db.py
from pathlib import Path
import sqlite3
from typing import Optional

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accounts (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  name              TEXT NOT NULL,
  institution       TEXT,
  currency          TEXT NOT NULL CHECK (length(currency) = 3),
  type              TEXT CHECK (type in ('checking','savings','card','cash','brokerage','other'))
                        DEFAULT 'checking',
  opening_balance   REAL NOT NULL DEFAULT 0,
  created_at_utc    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at_utc    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS transactions (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  date_utc          TEXT NOT NULL,
  amount            REAL NOT NULL,
  currency          TEXT NOT NULL CHECK (length(currency) = 3),
  category          TEXT NOT NULL,
  subcategory       TEXT,
  payee             TEXT,
  account_id        INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  direction         TEXT NOT NULL CHECK (direction in ('debit','credit')),
  notes             TEXT,
  tags_json         TEXT,
  created_at_utc    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at_utc    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  is_deleted        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_txn_date    ON transactions(date_utc);
CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_txn_cat     ON transactions(category);

CREATE TABLE IF NOT EXISTS fx_cache (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  date_utc          TEXT NOT NULL,
  base              TEXT NOT NULL CHECK (length(base) = 3),
  quote             TEXT NOT NULL CHECK (length(quote) = 3),
  rate              REAL NOT NULL CHECK (rate > 0),
  source            TEXT NOT NULL,
  retrieved_at_utc  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE(date_utc, base, quote)
);

CREATE TABLE IF NOT EXISTS settings (
  key        TEXT PRIMARY KEY,
  value_json TEXT NOT NULL
);
"""

def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)

def bootstrap(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn(db_path)
    init_db(conn)
    return conn

def add_account(conn: sqlite3.Connection, name: str, institution: Optional[str], currency: str,
                type: str = "checking", opening_balance: float = 0.0) -> int:
    cur = conn.execute(
        "INSERT INTO accounts(name,institution,currency,type,opening_balance) VALUES(?,?,?,?,?)",
        (name, institution, currency.upper(), type, float(opening_balance)),
    )
    conn.commit()
    return cur.lastrowid

def add_transaction(conn: sqlite3.Connection, *, date_utc: str, amount: float, currency: str,
                    category: str, account_id: int, direction: str,
                    subcategory: Optional[str] = None, payee: Optional[str] = None,
                    notes: Optional[str] = None, tags_json: Optional[str] = None) -> int:
    cur = conn.execute(
        """INSERT INTO transactions
           (date_utc,amount,currency,category,subcategory,payee,account_id,direction,notes,tags_json)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (date_utc, float(amount), currency.upper(), category, subcategory, payee,
         int(account_id), direction, notes, tags_json),
    )
    conn.commit()
    return cur.lastrowid

def count_rows(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row["n"])
