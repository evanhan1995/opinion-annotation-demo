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


def test_send_annotated_case_card_contains_annotation_fields(tmp_path, monkeypatch):
    """录入研判通知应携带严重度/分流建议/情感/摘要等研判字段。"""
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
        sent = notify.send_annotated_case_card(
            annotation_result={
                "严重度评级": "P1", "分流建议": "持续观察",
                "情感分析": {"整体情感": "负面"}, "摘要": "某产品被投诉",
                "风险标签": ["产品质量", "消费者投诉"],
            },
            scraped_data={"来源平台": "小红书", "原文内容": "原始内容"},
            url="https://example.com/post/1",
        )

    assert sent == 1
    card = captured["body"]["card"]
    assert card["header"]["template"] == "blue"
    content = card["elements"][0]["text"]["content"]
    assert "严重度" in content and "P1" in content
    assert "分流建议" in content and "持续观察" in content
    assert "情感" in content and "负面" in content
    assert "某产品被投诉" in content
    assert "产品质量" in content


def test_send_annotated_case_card_urgent_uses_red(tmp_path, monkeypatch):
    """分流建议=立即处理 → 红色 error 紧急处置卡。"""
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
        sent = notify.send_annotated_case_card(
            annotation_result={"严重度评级": "P0", "分流建议": "立即处理", "摘要": "严重事故"},
            scraped_data={"来源平台": "微博"},
            url="https://example.com/post/2",
        )

    assert sent == 1
    card = captured["body"]["card"]
    assert card["header"]["template"] == "red"
    assert "严重事故" in card["elements"][0]["text"]["content"]


def test_ingest_notify_switch(tmp_path, monkeypatch):
    """ingest 默认不通知，notify=True 时才推送（通知绑定录入研判提交）。"""
    import engine.ingestor as ing
    import engine.index_mgr as idxmgr

    calls = []
    monkeypatch.setattr(notify, "send_annotated_case_card",
                        lambda **kw: calls.append(kw) or 1)

    # 隔离文件系统写入，避免污染真实 wiki/
    cases = tmp_path / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ing, "CASES_DIR", cases)
    monkeypatch.setattr(ing, "INDEX_PATH", tmp_path / "index.md")
    monkeypatch.setattr(ing, "GLOBAL_INDEX_PATH", tmp_path / "global_index.md")
    monkeypatch.setattr(ing, "LOG_PATH", tmp_path / "log.md")
    monkeypatch.setattr(ing, "RAW_CASES_DIR", tmp_path / "raw_cases")
    monkeypatch.setattr(ing, "RAW_ARCHIVE_DIR", tmp_path / "raw_archive")
    monkeypatch.setattr(ing, "AUTHORS_DIR", tmp_path / "authors")
    (tmp_path / "global_index.md").write_text("", encoding="utf-8")
    monkeypatch.setattr(idxmgr, "update_case_index", lambda **kw: None)

    scraped = {"原文内容": "内容", "来源平台": "微博", "社媒数据": {}}
    ann = {"严重度评级": "P2", "分流建议": "持续观察", "摘要": "摘要",
           "情感分析": {"整体情感": "负面"}}

    # 默认 notify=False → 不通知
    ing.ingest(scraped, ann, "https://example.com/a")
    assert len(calls) == 0

    # notify=True → 通知一次
    ing.ingest(scraped, ann, "https://example.com/b", notify=True)
    assert len(calls) == 1
    assert calls[0]["annotation_result"]["严重度评级"] == "P2"
