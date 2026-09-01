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
    with pytest.raises(LLMUnavailable):
        propose_patch(issue=_issue(), failing_test="t", traceback="tb", files={})
