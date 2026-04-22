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


def test_generate_daily_report_persists_result(settings_factory, sample_bars, monkeypatch):
    settings = settings_factory(anthropic_api_key="test-key")
    db.init_db(settings.database_path)
    db.add_watchlist_item(settings.database_path, "600519", "贵州茅台")
    db.upsert_daily_bars(settings.database_path, "600519", sample_bars)

    captured: dict = {}

    def fake_anthropic(api_key: str):
        return _FakeAnthropic(api_key=api_key, text="# 今日自选股日报\n## 今日总览\n- 测试日报", capture=captured)

    monkeypatch.setattr(report_generator.anthropic, "Anthropic", fake_anthropic)

    report = report_generator.generate_daily_report(settings)

    assert report["report_markdown"].startswith("# 今日自选股日报")
    assert report["model_name"] == "claude-opus-4-6"
    assert captured["model"] == "claude-opus-4-6"
    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}

    saved = db.get_latest_report(settings.database_path)
    assert saved is not None
    assert saved["report_markdown"] == report["report_markdown"]
