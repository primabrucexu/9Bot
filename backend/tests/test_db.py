from __future__ import annotations

import sqlite3

from app import db


def test_init_db_creates_universe_and_sync_state_tables(settings_factory):
    settings = settings_factory()

    db.init_db(settings.database_path)

    with sqlite3.connect(str(settings.database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }

    assert "stock_universe" in tables
    assert "market_sync_state" in tables
    assert "idx_daily_bars_trade_date" in indexes
    assert "idx_daily_bars_trade_date_symbol" in indexes
    assert "idx_stock_universe_active_symbol" in indexes


def test_upsert_stock_universe_persists_and_updates_rows(settings_factory):
    settings = settings_factory()
    db.init_db(settings.database_path)

    inserted = db.upsert_stock_universe(
        settings.database_path,
        [
            {
                "symbol": "000001",
                "name": "平安银行",
                "market": "SZSE",
                "board": "main",
                "is_st": False,
                "is_active": True,
            },
            {
                "symbol": "688981",
                "name": "中芯国际",
                "market": "SSE",
                "board": "star",
                "is_st": False,
                "is_active": False,
            },
        ],
    )

    db.upsert_stock_universe(
        settings.database_path,
        [
            {
                "symbol": "688981",
                "name": "中芯国际-U",
                "market": "SSE",
                "board": "star",
                "is_st": False,
                "is_active": True,
            }
        ],
    )

    assert inserted == 2
    assert db.list_stock_universe(settings.database_path) == [
        {
            "symbol": "000001",
            "name": "平安银行",
            "market": "SZSE",
            "board": "main",
            "is_st": False,
            "is_active": True,
            "updated_at": db.get_stock_universe_item(settings.database_path, "000001")["updated_at"],
        },
        {
            "symbol": "688981",
            "name": "中芯国际-U",
            "market": "SSE",
            "board": "star",
            "is_st": False,
            "is_active": True,
            "updated_at": db.get_stock_universe_item(settings.database_path, "688981")["updated_at"],
        },
    ]


def test_list_stock_universe_supports_inactive_filter_and_pagination(settings_factory):
    settings = settings_factory()
    db.init_db(settings.database_path)
    db.upsert_stock_universe(
        settings.database_path,
        [
            {
                "symbol": "000001",
                "name": "平安银行",
                "market": "SZSE",
                "board": "main",
                "is_st": False,
                "is_active": True,
            },
            {
                "symbol": "000002",
                "name": "万科A",
                "market": "SZSE",
                "board": "main",
                "is_st": False,
                "is_active": False,
            },
            {
                "symbol": "000003",
                "name": "样本股",
                "market": "SZSE",
                "board": "main",
                "is_st": True,
                "is_active": True,
            },
        ],
    )

    active_rows = db.list_stock_universe(settings.database_path)
    paged_rows = db.list_stock_universe(settings.database_path, active_only=False, limit=1, offset=1)

    assert [row["symbol"] for row in active_rows] == ["000001", "000003"]
    assert len(paged_rows) == 1
    assert paged_rows[0]["symbol"] == "000002"
    assert paged_rows[0]["is_active"] is False
    assert paged_rows[0]["is_st"] is False


def test_replace_market_sync_state_upserts_by_scope(settings_factory):
    settings = settings_factory()
    db.init_db(settings.database_path)

    db.replace_market_sync_state(
        settings.database_path,
        "full-a-share",
        status="running",
        last_trade_date="2026-04-29",
    )
    db.replace_market_sync_state(
        settings.database_path,
        "full-a-share",
        status="failed",
        last_trade_date="2026-04-30",
        error="AkShare timeout",
    )

    state = db.get_market_sync_state(settings.database_path, "full-a-share")
    states = db.list_market_sync_states(settings.database_path)

    assert state is not None
    assert state["scope"] == "full-a-share"
    assert state["status"] == "failed"
    assert state["last_trade_date"] == "2026-04-30"
    assert state["error"] == "AkShare timeout"
    assert len(states) == 1
    assert states[0]["scope"] == "full-a-share"
