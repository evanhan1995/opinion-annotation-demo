# -*- coding: utf-8 -*-
"""Phase: MediaCrawler Douyin adapter tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.douyin_adapter import (
    _check_cookie_valid,
    search_douyin,
    fetch_douyin_note,
    _format_douyin_note,
    _format_search_item,
    _extract_video_id,
)

REQUIRED_KEYS = [
    "原文内容", "来源平台", "发布者类型", "互动数据",
    "发布时间", "原文链接", "评论列表", "社媒数据", "_meta",
]

TT_TEST_URL = "https://www.douyin.com/video/7645336397187943722"
TT_VIDEO_ID = "7645336397187943722"


class TestDouyinAdapter:
    """Verify MediaCrawler DouYinClient adapter."""

    def test_extract_video_id_standard(self):
        assert _extract_video_id(TT_TEST_URL) == TT_VIDEO_ID

    def test_extract_video_id_modal(self):
        url = f"https://www.douyin.com/jingxuan?modal_id={TT_VIDEO_ID}"
        assert _extract_video_id(url) == TT_VIDEO_ID

    def test_extract_video_id_any_19_digits(self):
        assert _extract_video_id(f"https://example.com/{TT_VIDEO_ID}") == TT_VIDEO_ID

    def test_format_search_item_structure(self):
        fake_item = {
            "aweme_info": {
                "desc": "Test video",
                "aweme_id": "1234567890123456789",
                "create_time": 1717977600,
                "author": {"nickname": "test_user"},
                "statistics": {"digg_count": 100},
            }
        }
        result = _format_search_item(fake_item)
        assert result["title"] == "Test video"
        assert result["url"] == "https://www.douyin.com/video/1234567890123456789"
        assert result["author"] == "test_user"
        assert result["engagement"] == 100

    def test_format_douyin_note_schema(self):
        fake_raw = {
            "desc": "测试视频",
            "aweme_id": "123",
            "author": {
                "nickname": "测试用户", "sec_uid": "abc", "uid": "123",
                "follower_count": 100, "signature": "简介",
            },
            "statistics": {
                "digg_count": 100, "comment_count": 10,
                "collect_count": 5, "share_count": 3, "play_count": 1000,
            },
            "duration": 60000,
            "create_time": 1717977600,
            "text_extra": [{"hashtag_name": "测试"}, {"hashtag_name": "标签"}],
        }
        formatted = _format_douyin_note(fake_raw, TT_TEST_URL)
        assert formatted["来源平台"] == "抖音"
        assert formatted["社媒数据"]["作者"] == "测试用户"
        assert formatted["社媒数据"]["粉丝"] == 100
        assert formatted["社媒数据"]["点赞"] == 100
        assert formatted["_meta"]["source"] == "mediacrawler-douyin"
        assert formatted["原文链接"] == TT_TEST_URL

    def test_format_douyin_note_all_keys(self):
        fake_raw = {
            "desc": "test", "aweme_id": "1",
            "author": {"nickname": "u"},
            "statistics": {},
            "duration": 0,
            "create_time": 1717977600,
            "text_extra": [],
        }
        formatted = _format_douyin_note(fake_raw, TT_TEST_URL)
        for k in REQUIRED_KEYS:
            assert k in formatted, f"Missing key: {k}"

    @pytest.mark.skipif(not _check_cookie_valid(), reason="Douyin cookie not configured")
    def test_search_live(self):
        results = search_douyin("Temu", count=5, sort_type="date")
        assert isinstance(results, list)
        if len(results) > 0:
            r = results[0]
            assert "title" in r
            assert "url" in r
            assert "author" in r

    @pytest.mark.skipif(not _check_cookie_valid(), reason="Douyin cookie not configured")
    def test_fetch_note_live(self):
        result = fetch_douyin_note(TT_TEST_URL, max_comments=3)
        for k in REQUIRED_KEYS:
            assert k in result, f"Missing key: {k}"
        assert result["来源平台"] == "抖音"
        assert result["_meta"]["video_id"] == TT_VIDEO_ID
        assert "_scrape_error" not in result
        assert len(result["原文内容"]) > 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
