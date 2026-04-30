from __future__ import annotations

import json
from typing import Any

import anthropic

from app import db
from app.config import Settings
from app.services import indicators, prompt_builder


class ReportGenerationError(Exception):
    pass


def generate_daily_report(settings: Settings) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        raise ReportGenerationError("请先在 conf/.env 中配置 ANTHROPIC_API_KEY，再生成 AI 日报。")

    report_context = build_report_context(settings)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=settings.report_max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[
                {
                    "type": "text",
                    "text": prompt_builder.REPORT_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": prompt_builder.build_report_user_message(report_context),
                }
            ],
        ) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise ReportGenerationError("Anthropic API Key 无效，请检查 conf/.env 配置。") from exc
    except anthropic.PermissionDeniedError as exc:
        raise ReportGenerationError("当前 Anthropic API Key 没有足够权限生成日报。") from exc
    except anthropic.RateLimitError as exc:
        raise ReportGenerationError("Anthropic 接口限流了，稍后再试。") from exc
    except anthropic.APIError as exc:
        raise ReportGenerationError(f"Anthropic 接口调用失败：{exc}") from exc

    report_markdown = "\n\n".join(
        block.text.strip() for block in response.content if block.type == "text" and block.text.strip()
    ).strip()
    if not report_markdown:
        raise ReportGenerationError("模型没有返回可用日报内容，请稍后重试。")

    db.save_daily_report(
        settings.database_path,
        report_context["report_date"],
        report_markdown,
        json.dumps(report_context, ensure_ascii=False, sort_keys=True),
        settings.anthropic_model,
    )

    saved_report = db.get_report_by_date(settings.database_path, report_context["report_date"])
    if saved_report is None:
        raise ReportGenerationError("日报生成成功，但写入本地数据库失败。")
    return saved_report


def build_report_context(settings: Settings) -> dict[str, Any]:
    universe = db.list_stock_universe(settings.database_path, active_only=True)
    if not universe:
        raise ReportGenerationError("请先刷新全市场股票清单并同步行情，再生成日报。")

    stocks: list[dict[str, Any]] = []
    for item in universe:
        bars = db.get_daily_bars(settings.database_path, item["symbol"], limit=180)
        if bars.empty:
            continue

        latest = indicators.summarize_latest(bars)
        stocks.append(
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "market": item["market"],
                "board": item["board"],
                "trade_date": latest["trade_date"],
                "close": latest["close"],
                "daily_change_pct": latest["daily_change_pct"],
                "ma5": latest["ma5"],
                "ma10": latest["ma10"],
                "ma20": latest["ma20"],
                "ma60": latest["ma60"],
                "rsi14": latest["rsi14"],
                "rsi_state": latest["rsi_state"],
                "macd_bias": latest["macd_bias"],
                "is_above_ma20": latest["is_above_ma20"],
                "signals": latest["signals"],
            }
        )

    if not stocks:
        raise ReportGenerationError("当前市场数据还没有可用行情，请先同步日线数据。")

    report_date = max(stock["trade_date"] for stock in stocks)
    report_stocks = [stock for stock in stocks if stock["trade_date"] == report_date]
    ordered = sorted(report_stocks, key=lambda item: item["daily_change_pct"] or 0, reverse=True)
    rising = sum(1 for stock in report_stocks if (stock["daily_change_pct"] or 0) > 0)
    falling = sum(1 for stock in report_stocks if (stock["daily_change_pct"] or 0) < 0)
    flat = len(report_stocks) - rising - falling
    avg_change = round(sum((stock["daily_change_pct"] or 0) for stock in report_stocks) / len(report_stocks), 2)
    strong_trend = [
        stock for stock in ordered if stock["is_above_ma20"] and stock["macd_bias"] == "多头"
    ]
    weak_trend = [
        stock for stock in sorted(ordered, key=lambda item: item["daily_change_pct"] or 0)
        if not stock["is_above_ma20"] and stock["macd_bias"] == "空头"
    ]

    return {
        "report_date": report_date,
        "scope": "full-a-share",
        "stock_count": len(report_stocks),
        "rising_count": rising,
        "falling_count": falling,
        "flat_count": flat,
        "average_change_pct": avg_change,
        "market_breakdown": _build_market_distribution(report_stocks, "market"),
        "board_breakdown": _build_market_distribution(report_stocks, "board"),
        "top_gainers": _compact_stocks(ordered[:5]),
        "top_losers": _compact_stocks(sorted(ordered, key=lambda item: item["daily_change_pct"] or 0)[:5]),
        "strong_trend": _compact_stocks(strong_trend[:5]),
        "weak_trend": _compact_stocks(weak_trend[:5]),
    }


def _build_market_distribution(stocks: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for stock in stocks:
        key = str(stock[field])
        counts[key] = counts.get(key, 0) + 1
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]



def _compact_stocks(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "market": stock.get("market"),
            "board": stock.get("board"),
            "daily_change_pct": stock["daily_change_pct"],
            "signals": stock["signals"][:3],
        }
        for stock in stocks
    ]
