# -*- coding: utf-8 -*-
"""Phase 1 tests: XHS-Downloader adapter round-trip verification.

Information-theoretic principle ([[feedback_roundtrip_test.md]]):
Every write/read pair must be tested for encoding-decoding consistency.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.xhs_fetcher import (
    _XHS_DL_AVAILABLE,
    _fetch_xhs_metadata_via_downloader,
    _format_xhs_dl_metadata,
    _format_xhshow_metadata,
    _assemble_result,
    fetch_xhs_note,
    parse_note_url,
)

# Shared test URL from project memory
XHS_TEST_URL = (
    "https://www.xiaohongshu.com/explore/69fb1fab00000000350304b8"
    "?xsec_token=ABWQXFsW9UXuyv041_3Ki-VJgALJ4qOf6FZXefk7aTsYo="
    "&xsec_source=pc_collect"
)
XHS_NOTE_ID = "69fb1fab00000000350304b8"

REQUIRED_KEYS = [
    "原文内容", "来源平台", "发布者类型", "互动数据",
    "发布时间", "原文链接", "评论列表", "社媒数据", "_meta",
]
SOCIAL_DATA_KEYS = ["作者", "国家", "点赞", "评论", "粉丝", "播放量", "作者主页"]


class TestXhsDownloaderAdapter:
    """Verify XHS-Downloader integration produces correct schema."""

    @pytest.mark.skipif(not _XHS_DL_AVAILABLE, reason="XHS-Downloader not installed")
    def test_metadata_fetch_returns_dict(self):
        """Channel 1: metadata extraction returns valid dict."""
        raw = _fetch_xhs_metadata_via_downloader(XHS_TEST_URL)
        assert raw is not None, "XHS-Downloader metadata fetch failed"
        assert isinstance(raw, dict), f"Expected dict, got {type(raw)}"
        assert "作品标题" in raw or "作品ID" in raw, "Missing expected XHS-DL keys"

    @pytest.mark.skipif(not _XHS_DL_AVAILABLE, reason="XHS-Downloader not installed")
    def test_format_xhs_dl_metadata(self):
        """Channel 1→2: metadata format preserves all required fields."""
        raw = _fetch_xhs_metadata_via_downloader(XHS_TEST_URL)
        assert raw is not None
        formatted = _format_xhs_dl_metadata(raw, XHS_NOTE_ID)
        for k in ["原文内容", "发布者类型", "互动数据", "发布时间", "社媒数据", "_meta"]:
            assert k in formatted, f"Missing key in formatted output: {k}"
        assert formatted["_meta"]["source"] == "xhs-downloader"

    @pytest.mark.skipif(not _XHS_DL_AVAILABLE, reason="XHS-Downloader not installed")
    def test_assemble_preserves_schema(self):
        """Channel 2→3: assembly maintains complete output schema."""
        raw = _fetch_xhs_metadata_via_downloader(XHS_TEST_URL)
        assert raw is not None
        formatted = _format_xhs_dl_metadata(raw, XHS_NOTE_ID)
        result = _assemble_result(formatted, XHS_TEST_URL, [])
        for k in REQUIRED_KEYS:
            assert k in result, f"Missing required key: {k}"
        assert result["来源平台"] == "小红书"
        assert result["原文链接"] == XHS_TEST_URL

    @pytest.mark.skipif(not _XHS_DL_AVAILABLE, reason="XHS-Downloader not installed")
    def test_full_pipeline_returns_valid_output(self):
        """End-to-end: fetch_xhs_note returns schema-compliant dict."""
        result = fetch_xhs_note(XHS_TEST_URL, max_comments=5)
        for k in REQUIRED_KEYS:
            assert k in result, f"Missing required key: {k}"
        assert result["来源平台"] == "小红书"
        assert result["_meta"]["note_id"] == XHS_NOTE_ID
        assert "_scrape_error" not in result, f"Unexpected error: {result.get('_scrape_error')}"

    @pytest.mark.skipif(not _XHS_DL_AVAILABLE, reason="XHS-Downloader not installed")
    def test_social_data_keys_complete(self):
        """Social data sub-schema has all keys (even if some are defaults)."""
        result = fetch_xhs_note(XHS_TEST_URL, max_comments=5)
        sd = result.get("社媒数据", {})
        for k in SOCIAL_DATA_KEYS:
            assert k in sd, f"Missing social data key: {k}"

    @pytest.mark.skipif(not _XHS_DL_AVAILABLE, reason="XHS-Downloader not installed")
    def test_content_quality_non_empty(self):
        """Content fields are non-trivial."""
        result = fetch_xhs_note(XHS_TEST_URL, max_comments=5)
        assert len(result["原文内容"]) > 50, "Content too short"
        assert result["发布者类型"], "Author info empty"
        assert result["发布时间"], "Publish time empty"
        assert result["社媒数据"]["点赞"] > 0, "Like count zero"

    def test_parse_note_url(self):
        """URL parsing extracts correct fields."""
        parsed = parse_note_url(XHS_TEST_URL)
        assert parsed["note_id"] == XHS_NOTE_ID
        assert parsed["xsec_token"].startswith("ABWQ")
        assert parsed["xsec_source"] == "pc_collect"

    def test_assemble_with_comments(self):
        """Comments are correctly formatted in output."""
        fake_formatted = {
            "原文内容": "标题：测试\n\n正文：test",
            "发布者类型": "小红书用户: tester (123)",
            "互动数据": "点赞10, 收藏5, 评论3, 分享2",
            "发布时间": "2026-01-01",
            "社媒数据": {
                "作者": "tester", "国家": "", "点赞": 10,
                "评论": 3, "粉丝": 100, "播放量": None,
                "作者主页": [], "_播放量估算": True,
            },
            "_meta": {"note_id": "123", "source": "test"},
        }
        fake_comments = [
            {"content": "好内容", "like_count": "5"},
            {"content": "学习了", "like_count": "2"},
        ]
        result = _assemble_result(fake_formatted, "http://x.com/123", fake_comments)
        assert len(result["评论列表"]) == 2
        assert result["评论列表"][0]["内容"] == "好内容"
        assert result["评论列表"][0]["点赞"] == "5"

    def test_format_xhshow_metadata_backward_compat(self):
        """xhshow path (fallback) still produces correct schema."""
        fake_note = {
            "title": "测试笔记",
            "desc": "测试正文",
            "user": {"nickname": "testuser", "user_id": "u123", "follower_count": 500},
            "interact_info": {
                "liked_count": "100", "collected_count": "50",
                "comment_count": "10", "share_count": "20",
            },
            "ip_location": "北京",
            "time": 1717977600000,
            "tag_list": [{"name": "AI"}, {"name": "技术"}],
        }
        formatted = _format_xhshow_metadata(fake_note, "n123")
        assert "原文内容" in formatted
        assert "标签：#AI #技术" in formatted["原文内容"]
        assert formatted["社媒数据"]["粉丝"] == 500
        assert formatted["社媒数据"]["国家"] == "北京"
        assert formatted["_meta"]["source"] == "xhshow"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
