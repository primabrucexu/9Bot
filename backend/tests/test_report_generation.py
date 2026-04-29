from __future__ import annotations

from dataclasses import replace

from app import db
from app.services import report_generator


class _FakeMessage:
    def __init__(self, text: str):
        self.content = [type("TextBlock", (), {"type": "text", "text": text})()]


class _FakeStream:
    def __init__(self, text: str):
        self._message = _FakeMessage(text)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_final_message(self):
        return self._message


class _FakeMessages:
    def __init__(self, text: str, capture: dict):
        self._text = text
        self._capture = capture

    def stream(self, **kwargs):
        self._capture.update(kwargs)
        return _FakeStream(self._text)


class _FakeAnthropic:
    def __init__(self, *, api_key: str, text: str, capture: dict):
        self.api_key = api_key
        self.messages = _FakeMessages(text, capture)


def test_build_report_context_summarizes_latest_synced_market(settings_factory, sample_bars):
    settings = settings_factory()
    db.init_db(settings.database_path)
    db.upsert_stock_universe(
        settings.database_path,
        [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "SSE",
                "board": "main",
                "is_st": False,
                "is_active": True,
            },
            {
                "symbol": "000001",
                "name": "平安银行",
                "market": "SZSE",
                "board": "main",
                "is_st": False,
                "is_active": True,
            },
        ],
    )
    lagging_bars = sample_bars.copy()
    lagging_bars.loc[lagging_bars.index[-1], "close"] = float(sample_bars.iloc[-2]["close"] - 1.2)
    lagging_bars.loc[lagging_bars.index[-1], "open"] = float(sample_bars.iloc[-2]["close"] - 0.8)
    lagging_bars.loc[lagging_bars.index[-1], "high"] = float(sample_bars.iloc[-2]["close"] - 0.4)
    lagging_bars.loc[lagging_bars.index[-1], "low"] = float(sample_bars.iloc[-2]["close"] - 1.6)

    db.upsert_daily_bars(settings.database_path, "600519", sample_bars)
    db.upsert_daily_bars(settings.database_path, "000001", lagging_bars)

    context = report_generator.build_report_context(settings)

    assert context["scope"] == "full-a-share"
    assert context["stock_count"] == 2
    assert context["report_date"] == sample_bars.iloc[-1]["trade_date"].strftime("%Y-%m-%d")
    assert context["top_gainers"][0]["symbol"] == "600519"
    assert context["top_losers"][0]["symbol"] == "000001"
    assert context["market_breakdown"] == [{"name": "SSE", "count": 1}, {"name": "SZSE", "count": 1}]



def test_generate_daily_report_persists_result(settings_factory, sample_bars, monkeypatch):
    settings = settings_factory(anthropic_api_key="test-key")
    db.init_db(settings.database_path)
    db.upsert_stock_universe(
        settings.database_path,
        [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "SSE",
                "board": "main",
                "is_st": False,
                "is_active": True,
            }
        ],
    )
    db.upsert_daily_bars(settings.database_path, "600519", sample_bars)

    captured: dict = {}

    def fake_anthropic(api_key: str):
        return _FakeAnthropic(api_key=api_key, text="# 今日市场观察日报\n## 今日总览\n- 测试日报", capture=captured)

    monkeypatch.setattr(report_generator.anthropic, "Anthropic", fake_anthropic)

    report = report_generator.generate_daily_report(settings)

    assert report["report_markdown"].startswith("# 今日市场观察日报")
    assert report["model_name"] == "claude-opus-4-6"
    assert captured["model"] == "claude-opus-4-6"
    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}

    saved = db.get_latest_report(settings.database_path)
    assert saved is not None
    assert saved["report_markdown"] == report["report_markdown"]
