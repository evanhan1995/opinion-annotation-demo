# -*- coding: utf-8 -*-
"""JSON extraction tests for engine/annotate.py extract_json_from_response.

Note: extract_json_from_response returns a JSON *string* (not parsed dict).
Parsing is handled separately by safe_json_parse / extract_json in agents/shared.py.
"""

import json
import pytest
from engine.annotate import extract_json_from_response


class TestExtractJson:
    """Verify extract_json_from_response handles all known LLM output forms."""

    def test_plain_json_object(self):
        text = extract_json_from_response('{"key": "value", "num": 42}')
        parsed = json.loads(text)
        assert parsed == {"key": "value", "num": 42}

    def test_plain_json_array(self):
        text = extract_json_from_response("[1, 2, 3]")
        assert text == "[1, 2, 3]"

    def test_json_fence(self):
        text = extract_json_from_response('```json\n{"a": 1}\n```')
        parsed = json.loads(text)
        assert parsed == {"a": 1}

    def test_json_fence_no_lang(self):
        text = extract_json_from_response('```\n{"b": 2}\n```')
        assert text == '{"b": 2}'

    def test_fence_with_array(self):
        text = extract_json_from_response('```json\n[4, 5]\n```')
        assert text == "[4, 5]"

    def test_prose_before_json(self):
        text = extract_json_from_response("some chat text here\n{\"result\": true}\nmore text")
        parsed = json.loads(text)
        assert parsed == {"result": True}

    def test_nested_object(self):
        text = extract_json_from_response(
            '{"severity": "P1", "risk_tags": ["合规", "隐私"], "sentiment": "负面"}'
        )
        parsed = json.loads(text)
        assert parsed["severity"] == "P1"
        assert len(parsed["risk_tags"]) == 2

    def test_no_json_at_all(self):
        text = extract_json_from_response("this is just plain text with no json")
        assert text == "this is just plain text with no json"

    def test_empty_string(self):
        text = extract_json_from_response("")
        assert text == ""

    def test_boolean_and_null_values(self):
        text = extract_json_from_response('{"active": true, "note": null, "count": 0}')
        parsed = json.loads(text)
        assert parsed == {"active": True, "note": None, "count": 0}

    def test_chinese_text_in_json(self):
        text = extract_json_from_response(
            '{"严重度评级": "P2", "摘要": "这是一条中文摘要", "舆情分类": ["产品质量", "客户投诉"]}'
        )
        parsed = json.loads(text)
        assert parsed["严重度评级"] == "P2"
        assert "客户投诉" in parsed["舆情分类"]

    def test_bracketed_array_extraction(self):
        text = extract_json_from_response('```json\n["tag1", "tag2", "tag3"]\n```')
        assert text == '["tag1", "tag2", "tag3"]'
