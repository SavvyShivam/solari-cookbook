from __future__ import annotations

import pytest

from repro_agent.llm import LLMUnavailable, build_patch_prompt, extract_diff, propose_patch
from repro_agent.models import Issue


def _issue():
    return Issue(url="u", title="bug", body="b", repo_url="r", owner="o", repo="c",
                 expected="empty", actual="all rows")


def test_extract_diff_from_fence():
    reply = "Here is the fix:\n```diff\n--- a/app.py\n+++ b/app.py\n@@\n-x\n+y\n```\nDone."
    assert extract_diff(reply) == "--- a/app.py\n+++ b/app.py\n@@\n-x\n+y"


def test_extract_diff_bare():
    reply = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-a\n+b\n"
    assert extract_diff(reply).startswith("--- a/app.py")


def test_extract_diff_none_raises():
    with pytest.raises(ValueError):
        extract_diff("no diff here, sorry")


def test_build_patch_prompt_includes_context():
    p = build_patch_prompt(_issue(), "def test_x(): ...", "Traceback ...", {"app.py": "code"})
    assert "def test_x()" in p and "app.py" in p and "unified diff" in p.lower()


def test_propose_patch_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMUnavailable):
        propose_patch(issue=_issue(), failing_test="t", traceback="tb", files={})


def test_complete_uses_groq_when_key_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "```diff\n--- a\n+++ b\n```"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["model"] = json["model"]
        captured["auth"] = headers["Authorization"]
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)
    diff = propose_patch(issue=_issue(), failing_test="t", traceback="tb", files={})
    assert diff == "--- a\n+++ b"
    assert captured["url"].startswith("https://api.groq.com/")
    assert captured["model"] == "llama-3.3-70b-versatile"
    assert captured["auth"] == "Bearer gsk_test"
