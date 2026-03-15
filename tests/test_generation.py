"""Tests for generation helpers (e.g. _clean_json)."""

import json

import pytest

from core.generation import _clean_json


def test_clean_json_strips_markdown():
    raw = '```json\n{"a": 1}\n```'
    assert json.loads(_clean_json(raw)) == {"a": 1}


def test_clean_json_plain():
    raw = '{"b": 2}'
    assert json.loads(_clean_json(raw)) == {"b": 2}


def test_clean_json_extra_text():
    raw = 'Here is the result:\n```\n{"c": 3}\n```'
    assert json.loads(_clean_json(raw)) == {"c": 3}
