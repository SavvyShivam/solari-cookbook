from __future__ import annotations

import pytest

from repro_agent.llm import (
    LLMUnavailable,
    build_patch_prompt,
    parse_file_blocks,
    propose_file_edits,
)
from repro_agent.models import Issue


def _issue():
    return Issue(url="u", title="bug", body="b", repo_url="r", owner="o", repo="c",
                 expected="empty", actual="all rows")


def test_parse_file_blocks_file_prefix():
    reply = "Sure.\nFile: app.py\n```python\nx = 1\n```\nDone."
    assert parse_file_blocks(reply) == {"app.py": "x = 1\n"}


def test_parse_file_blocks_hash_prefix_and_multiple():
    reply = "### src/a.py\n```\na\n```\n\n### src/b.py\n```python\nb\n```\n"
    assert parse_file_blocks(reply) == {"src/a.py": "a\n", "src/b.py": "b\n"}


def test_parse_file_blocks_none():
    assert parse_file_blocks("no file blocks here") == {}


def test_build_patch_prompt_asks_for_whole_files():
    p = build_patch_prompt(_issue(), "def test_x(): ...", "Traceback ...", {"app.py": "code"})
    assert "def test_x()" in p and "app.py" in p
    assert "File: <path>" in p and "Do NOT output a diff" in p


def test_propose_file_edits_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMUnavailable):
        propose_file_edits(issue=_issue(), failing_test="t", traceback="tb", files={})


def test_propose_file_edits_uses_groq_when_key_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "File: app.py\n```python\nfixed = 1\n```"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["model"] = json["model"]
        captured["auth"] = headers["Authorization"]
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)
    edits = propose_file_edits(issue=_issue(), failing_test="t", traceback="tb", files={})
    assert edits == {"app.py": "fixed = 1\n"}
    assert captured["url"].startswith("https://api.groq.com/")
    assert captured["model"] == "openai/gpt-oss-120b"
    assert captured["auth"] == "Bearer gsk_test"
