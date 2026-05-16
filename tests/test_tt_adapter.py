# -*- coding: utf-8 -*-
"""Phase 3 tests: TikTok/Douyin adapter round-trip verification."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.tt_fetcher import (
    _TT_AVAILABLE,
    _check_cookie_valid,
    extract_video_id,
    _format_douyin_metadata,
    _assemble_douyin_result,
    fetch_douyin_video,
)

REQUIRED_KEYS = [
    "原文内容", "来源平台", "发布者类型", "互动数据",
    "发布时间", "原文链接", "评论列表", "社媒数据", "_meta",
]

TT_TEST_URL = "https://www.douyin.com/video/7640102676776209690"
TT_VIDEO_ID = "7640102676776209690"


class TestDouyinAdapter:
    """Verify TikTokDownloader integration."""

    def test_extract_video_id_standard_url(self):
        """Parse /video/ID format."""
        assert extract_video_id(TT_TEST_URL) == TT_VIDEO_ID

    def test_extract_video_id_modal(self):
        """Parse jingxuan?modal_id= format."""
        url = f"https://www.douyin.com/jingxuan?modal_id={TT_VIDEO_ID}"
        assert extract_video_id(url) == TT_VIDEO_ID

    def test_extract_video_id_any_19_digits(self):
        """Parse any URL containing 19-digit ID."""
        assert extract_video_id(f"https://example.com/{TT_VIDEO_ID}") == TT_VIDEO_ID

    def test_format_metadata_schema(self):
        """Metadata formatting produces complete schema."""
        fake_raw = {
            "desc": "测试视频",
            "author": {"nickname": "测试用户", "sec_uid": "abc", "uid": "123",
                       "follower_count": 100, "signature": "简介"},
            "statistics": {"digg_count": 100, "comment_count": 10,
                           "collect_count": 5, "share_count": 3, "play_count": 1000},
            "duration": 60000,
            "create_time": 1717977600,
            "text_extra": [{"hashtag_name": "测试"}, {"hashtag_name": "标签"}],
        }
        formatted = _format_douyin_metadata(fake_raw, "123")
        assert "原文内容" in formatted
        assert "发布者类型" in formatted
        assert "社媒数据" in formatted
        assert formatted["社媒数据"]["粉丝"] == 100
        assert formatted["_meta"]["source"] == "tiktok-downloader"

    def test_assemble_schema_complete(self):
        """Assembly produces all required keys."""
        fake_formatted = {
            "原文内容": "标题：test",
            "发布者类型": "抖音用户: test",
            "互动数据": "点赞1",
            "发布时间": "2026-01-01",
            "社媒数据": {"作者": "t", "国家": "", "点赞": 1, "评论": 0, "粉丝": 0,
                          "播放量": None, "作者主页": []},
            "_meta": {"video_id": "1", "source": "test"},
        }
        result = _assemble_douyin_result(fake_formatted, "http://x.com", [])
        for k in REQUIRED_KEYS:
            assert k in result, f"Missing: {k}"
        assert result["来源平台"] == "抖音"

    def test_assemble_with_comments(self):
        """Comments are correctly formatted."""
        fake_formatted = {
            "原文内容": "标题：test",
            "发布者类型": "test",
            "互动数据": "点赞1",
            "发布时间": "2026-01-01",
            "社媒数据": {"作者": "", "国家": "", "点赞": 0, "评论": 0, "粉丝": 0,
                          "播放量": None, "作者主页": []},
            "_meta": {"video_id": "1", "source": "test"},
        }
        fake_comments = [
            {"text": "好视频", "digg_count": 5},
            {"text": "学习了", "digg_count": 2},
        ]
        result = _assemble_douyin_result(fake_formatted, "http://x.com", fake_comments)
        assert len(result["评论列表"]) == 2
        assert result["评论列表"][0]["内容"] == "好视频"
        assert result["评论列表"][0]["点赞"] == "5"

    @pytest.mark.skipif(not _TT_AVAILABLE, reason="TikTokDownloader not installed")
    @pytest.mark.skipif(not _check_cookie_valid(), reason="Douyin cookie not configured")
    def test_full_pipeline_live(self):
        """End-to-end live test with real douyin video."""
        result = fetch_douyin_video(TT_TEST_URL, max_comments=5)
        for k in REQUIRED_KEYS:
            assert k in result, f"Missing: {k}"
        assert result["来源平台"] == "抖音"
        assert result["_meta"]["video_id"] == TT_VIDEO_ID
        assert "_scrape_error" not in result
        assert len(result["原文内容"]) > 30
        assert result["社媒数据"]["点赞"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
