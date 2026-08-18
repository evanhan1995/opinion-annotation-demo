"""Feishu webhook notification tests."""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from shared import notify


def _write_config(tmp_path, webhooks, monkeypatch):
    cfg = {"desktop_alert": True, "webhooks": webhooks}
    path = tmp_path / "notification_config.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(notify, "_NOTIFY_CONFIG_PATH", path)


def test_load_webhooks_normalizes_dicts(tmp_path, monkeypatch):
    _write_config(tmp_path, [
        {"name": "群1", "url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc",
         "enabled": True, "trigger_level": "P0"},
    ], monkeypatch)

    hooks = notify._load_webhooks()

    assert len(hooks) == 1
    assert hooks[0]["url"].endswith("abc")


def test_load_webhooks_skips_disabled_and_placeholder(tmp_path, monkeypatch):
    _write_config(tmp_path, [
        {"name": "禁用", "url": "https://x/hook/disabled", "enabled": False, "trigger_level": "P0"},
        {"name": "占位", "url": "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_TOKEN",
         "enabled": True, "trigger_level": "P0"},
        {"name": "有效", "url": "https://x/hook/ok", "enabled": True, "trigger_level": "P0+P1"},
    ], monkeypatch)

    hooks = notify._load_webhooks()

    assert [h["url"] for h in hooks] == ["https://x/hook/ok"]


def test_send_feishu_card_posts_valid_payload(tmp_path, monkeypatch):
    _write_config(tmp_path, [
        {"name": "群1", "url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc",
         "enabled": True, "trigger_level": "P0"},
    ], monkeypatch)
    captured = {}

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return self._body

    def fake_urlopen(req, timeout=10):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(json.dumps({"code": 0, "msg": "success"}).encode("utf-8"))

    with mock.patch.object(notify.urllib.request, "urlopen", side_effect=fake_urlopen):
        sent = notify.send_feishu_card(
            title="测试",
            body_text="正文",
            fields={"P0": "1"},
            level="warning",
        )

    assert sent == 1
    assert captured["method"] == "POST"
    assert captured["url"].endswith("abc")
    card = captured["body"]["card"]
    assert card["header"]["template"] == "yellow"
    assert card["elements"][0]["tag"] == "div"
    assert card["elements"][0]["text"]["tag"] == "lark_md"
    assert card["elements"][1]["fields"][0]["is_short"] is True


def test_send_feishu_card_returns_zero_on_rejection(tmp_path, monkeypatch):
    _write_config(tmp_path, [
        {"name": "群1", "url": "https://x/hook/abc", "enabled": True, "trigger_level": "P0"},
    ], monkeypatch)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"code": 19001, "msg": "bad"}).encode("utf-8")

    with mock.patch.object(notify.urllib.request, "urlopen",
                           side_effect=lambda req, timeout=10: FakeResponse()):
        sent = notify.send_feishu_card(title="t", body_text="b")

    assert sent == 0


def test_send_feishu_card_skips_placeholder_url(monkeypatch):
    monkeypatch.setattr(notify, "_NOTIFY_CONFIG_PATH", Path("unused"))

    with mock.patch.object(notify.urllib.request, "urlopen") as urlopen:
        sent = notify.send_feishu_card(
            title="t",
            body_text="b",
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_TOKEN",
        )

    assert sent == 0
    urlopen.assert_not_called()


def test_send_new_pending_case_card_posts_metrics(tmp_path, monkeypatch):
    _write_config(tmp_path, [
        {"name": "群1", "url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc",
         "enabled": True, "trigger_level": "P0"},
    ], monkeypatch)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"code": 0, "msg": "success"}).encode("utf-8")

    def fake_urlopen(req, timeout=10):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    with mock.patch.object(notify.urllib.request, "urlopen", side_effect=fake_urlopen):
        sent = notify.send_new_pending_case_card(
            url="https://example.com/post/1",
            comments=12345,
            likes=678,
            collects=90,
            shares=12,
        )

    assert sent == 1
    card = captured["body"]["card"]
    content = card["elements"][0]["text"]["content"]
    assert "有新的待处理case" in content
    assert "链接：https://example.com/post/1" in content
    assert "评论：12,345" in content
    assert "点赞：678" in content
    assert "收藏：90" in content
    assert "转发：12" in content


def test_metric_text_fallback():
    assert notify._metric_text(None) == "0"
    assert notify._metric_text("") == "0"


def test_send_severity_card_respects_trigger_level(tmp_path, monkeypatch):
    _write_config(tmp_path, [
        {"name": "仅P0", "url": "https://x/hook/p0", "enabled": True, "trigger_level": "P0"},
        {"name": "P0+P1", "url": "https://x/hook/all", "enabled": True, "trigger_level": "P0+P1"},
    ], monkeypatch)
    hits = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"code": 0, "msg": "success"}).encode("utf-8")

    def fake_urlopen(req, timeout=10):
        hits.append(req.full_url)
        return FakeResponse()

    with mock.patch.object(notify.urllib.request, "urlopen", side_effect=fake_urlopen):
        sent = notify.send_severity_card(title="t", body_text="b", severity="P1")

    assert sent == 1
    assert hits == ["https://x/hook/all"]
