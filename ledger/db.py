from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Iterable, Tuple, Dict, Any

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

# ---------- Helpers for import/duplicate detection ----------

def get_accounts(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, currency FROM accounts WHERE 1 ORDER BY id"
    ).fetchall()

def get_txns_between(conn: sqlite3.Connection, account_id: int, start_iso: str, end_iso: str) -> List[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, date_utc, amount, currency, payee, category
        FROM transactions
        WHERE is_deleted=0
          AND account_id=?
          AND date_utc BETWEEN ? AND ?
        """,
        (int(account_id), start_iso, end_iso)
    ).fetchall()

def get_or_create_account(conn: sqlite3.Connection, *, name: str, currency: str,
                          type: str = "cash", opening_balance: float = 0.0) -> int:
    row = conn.execute(
        "SELECT id FROM accounts WHERE name=? AND currency=? LIMIT 1",
        (name, currency.upper()),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO accounts(name, institution, currency, type, opening_balance) VALUES(?,?,?,?,?)",
        (name, None, currency.upper(), type, float(opening_balance)),
    )
    conn.commit()
    return cur.lastrowid

def ensure_default_accounts(conn: sqlite3.Connection, currencies=("KRW","USD")) -> dict:
    """Ensure default per-currency accounts exist. Returns {currency: account_id}."""
    mapping = {}
    for cur in currencies:
        aid = get_or_create_account(conn, name=f"Default {cur}", currency=cur, type="cash", opening_balance=0.0)
        mapping[cur.upper()] = aid
    return mapping
def upsert_fx_cache_many(conn: sqlite3.Connection,
                         rows: Iterable[Tuple[str, str, str, float, str]]) -> int:
    """
    rows: iterable of (date_utc(YYYY-MM-DD), base, quote, rate, source)
    """
    n = 0
    for d, base, quote, rate, src in rows:
        conn.execute(
            """INSERT INTO fx_cache(date_utc, base, quote, rate, source)
               VALUES(?,?,?,?,?)
               ON CONFLICT(date_utc, base, quote)
               DO UPDATE SET rate=excluded.rate, source=excluded.source,
                             retrieved_at_utc=(strftime('%Y-%m-%dT%H:%M:%SZ','now'))""",
            (d, base.upper(), quote.upper(), float(rate), src),
        )
        n += 1
    conn.commit()
    return n

def get_latest_fx(conn: sqlite3.Connection, base: str, quote: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """SELECT date_utc, rate, source FROM fx_cache
           WHERE base=? AND quote=?
           ORDER BY date_utc DESC LIMIT 1""",
        (base.upper(), quote.upper()),
    ).fetchone()

def account_balances_native(conn: sqlite3.Connection, as_of_iso: Optional[str] = None):
    """
    각 계정의 원화/달러 '자체통화' 잔액을 계산하여 리스트로 반환.
    잔액 = opening_balance + (credit 합계) - (debit 합계)
    """
    date_filter = ""
    params = []
    if as_of_iso:
        date_filter = "AND t.date_utc <= ?"
        params.append(as_of_iso)

    q = f"""
    SELECT a.id, a.name, a.currency, a.opening_balance,
           COALESCE(SUM(CASE
                WHEN t.direction='credit' THEN t.amount
                WHEN t.direction='debit'  THEN -t.amount
                ELSE 0 END), 0) AS net_txn
    FROM accounts a
    LEFT JOIN transactions t
      ON t.account_id=a.id AND t.is_deleted=0 {date_filter}
    GROUP BY a.id, a.name, a.currency, a.opening_balance
    ORDER BY a.id
    """
    rows = conn.execute(q, params).fetchall()
    out = []
    for r in rows:
        bal = float(r["opening_balance"]) + float(r["net_txn"])
        out.append({
            "account_id": int(r["id"]),
            "name": str(r["name"]),
            "currency": str(r["currency"]).upper(),
            "balance_native": float(bal),
        })
    return out

def _fx_for_date_or_latest(conn: sqlite3.Connection, base: str, quote: str, date_str: str) -> Optional[float]:
    """
    해당 날짜의 환율이 없으면 '그 이전 최신'을 사용.
    """
    row = conn.execute(
        """SELECT rate FROM fx_cache
           WHERE base=? AND quote=? AND date_utc<=?
           ORDER BY date_utc DESC LIMIT 1""",
        (base.upper(), quote.upper(), date_str)
    ).fetchone()
    return float(row["rate"]) if row else None

def balances_in_base(conn: sqlite3.Connection, base: str = "KRW", as_of_iso: Optional[str] = None):
    """
    각 계정 원화/달러 잔액을 기준통화로 환산하여 리스트로 반환:
    [{name, currency, balance_native, balance_base}, ...], total_base 포함
    """
    base = base.upper()
    if as_of_iso is None:
        as_of_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    as_of_date = as_of_iso[:10]  # YYYY-MM-DD

    items = account_balances_native(conn, as_of_iso)
    result = []
    total = 0.0

    for it in items:
        cur = it["currency"].upper()
        nat = float(it["balance_native"])

        if cur == base:
            base_val = nat
        elif {cur, base} == {"USD", "KRW"}:
            r = _fx_for_date_or_latest(conn, "USD", "KRW", as_of_date)
            if r is None:
                base_val = None
            else:
                base_val = nat * r if base == "KRW" else (nat / r)
        else:
            base_val = None  # 미지원 통화쌍은 건너뜀 (MVP)

        result.append({
            **it,
            "balance_base": base_val
        })
        if base_val is not None:
            total += base_val

    return {"items": result, "total_base": total}