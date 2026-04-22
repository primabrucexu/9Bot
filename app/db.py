from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd


SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    note TEXT,
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL,
    amount REAL,
    PRIMARY KEY (symbol, trade_date)
);

CREATE TABLE IF NOT EXISTS daily_reports (
    report_date TEXT PRIMARY KEY,
    report_markdown TEXT NOT NULL,
    context_json TEXT NOT NULL,
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    return connection


def init_db(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(database_path) as connection:
        connection.executescript(SCHEMA)


def list_watchlist(database_path: Path) -> list[dict[str, Any]]:
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT symbol, name, note, sort_order, created_at
            FROM watchlist
            ORDER BY sort_order ASC, created_at ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_watchlist_item(database_path: Path, symbol: str) -> dict[str, Any] | None:
    with _connect(database_path) as connection:
        row = connection.execute(
            "SELECT symbol, name, note, sort_order, created_at FROM watchlist WHERE symbol = ?",
            (symbol,),
        ).fetchone()
    return dict(row) if row else None


def add_watchlist_item(database_path: Path, symbol: str, name: str, note: str | None = None) -> None:
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    with _connect(database_path) as connection:
        existing = connection.execute(
            "SELECT symbol FROM watchlist WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE watchlist SET name = ?, note = COALESCE(?, note) WHERE symbol = ?",
                (name, note, symbol),
            )
            return

        next_order = connection.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM watchlist"
        ).fetchone()["next_order"]
        connection.execute(
            """
            INSERT INTO watchlist(symbol, name, note, sort_order, created_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (symbol, name, note, next_order, timestamp),
        )


def update_watchlist_name(database_path: Path, symbol: str, name: str) -> None:
    with _connect(database_path) as connection:
        connection.execute(
            "UPDATE watchlist SET name = ? WHERE symbol = ?",
            (name, symbol),
        )


def delete_watchlist_item(database_path: Path, symbol: str) -> None:
    with _connect(database_path) as connection:
        connection.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))


def upsert_daily_bars(database_path: Path, symbol: str, bars: pd.DataFrame) -> None:
    if bars.empty:
        return

    records = []
    for row in bars.itertuples(index=False):
        trade_date = pd.Timestamp(row.trade_date).strftime("%Y-%m-%d")
        records.append(
            (
                symbol,
                trade_date,
                float(row.open),
                float(row.high),
                float(row.low),
                float(row.close),
                float(row.volume) if pd.notna(row.volume) else None,
                float(row.amount) if pd.notna(row.amount) else None,
            )
        )

    with _connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO daily_bars(symbol, trade_date, open, high, low, close, volume, amount)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount
            """,
            records,
        )


def get_daily_bars(database_path: Path, symbol: str, limit: int | None = None) -> pd.DataFrame:
    query = (
        "SELECT trade_date, open, high, low, close, volume, amount "
        "FROM daily_bars WHERE symbol = ? ORDER BY trade_date DESC"
    )
    params: list[Any] = [symbol]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    wrapped_query = f"SELECT * FROM ({query}) ORDER BY trade_date ASC"

    with _connect(database_path) as connection:
        bars = pd.read_sql_query(wrapped_query, connection, params=params, parse_dates=["trade_date"])

    if bars.empty:
        return bars

    numeric_columns = ["open", "high", "low", "close", "volume", "amount"]
    for column in numeric_columns:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    return bars


def save_daily_report(
    database_path: Path,
    report_date: str,
    report_markdown: str,
    context_json: str,
    model_name: str,
) -> None:
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO daily_reports(report_date, report_markdown, context_json, model_name, created_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(report_date) DO UPDATE SET
                report_markdown = excluded.report_markdown,
                context_json = excluded.context_json,
                model_name = excluded.model_name,
                created_at = excluded.created_at
            """,
            (report_date, report_markdown, context_json, model_name, timestamp),
        )


def get_latest_report(database_path: Path) -> dict[str, Any] | None:
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT report_date, report_markdown, context_json, model_name, created_at
            FROM daily_reports
            ORDER BY report_date DESC
            LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def get_report_by_date(database_path: Path, report_date: str) -> dict[str, Any] | None:
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT report_date, report_markdown, context_json, model_name, created_at
            FROM daily_reports
            WHERE report_date = ?
            """,
            (report_date,),
        ).fetchone()
    return dict(row) if row else None
