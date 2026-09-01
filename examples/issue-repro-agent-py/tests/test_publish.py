from __future__ import annotations

import asyncio

from repro_agent.models import FixResult, Issue, ReproResult
from repro_agent.publish import open_pr, pr_body, pr_title, publish
from repro_agent.workspace import Workspace
from tests.conftest import FakeSandbox


def _issue():
    return Issue(url="https://github.com/o/c/issues/7", title="limit=0 bug", body="b",
                 repo_url="https://github.com/o/c", owner="o", repo="c")


def _repro():
    return ReproResult("/work/repo/tests/test_repro_1.py", "def test_x(): ...", True, "boom")


def test_pr_title_labels_unresolved():
    assert "reproduced; fix unresolved" in pr_title(_issue(), FixResult("unresolved", "", 2, "")).lower()
    assert "unresolved" not in pr_title(_issue(), FixResult("green", "d", 1, "")).lower()


def test_pr_body_links_issue_and_shows_diff():
    body = pr_body(_issue(), _repro(), FixResult("green", "THE DIFF", 1, "ok"))
    assert "https://github.com/o/c/issues/7" in body and "THE DIFF" in body


def test_open_pr_posts_expected_payload():
    captured = {}

    class FakeResp:
        status_code = 201

        def json(self):
            return {"html_url": "https://github.com/o/c/pull/9"}

    class FakeHttp:
        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResp()

    url = asyncio.run(open_pr(_issue(), "repro/x", "T", "B", "tok", http=FakeHttp()))
    assert url == "https://github.com/o/c/pull/9"
    assert captured["url"] == "https://api.github.com/repos/o/c/pulls"
    assert captured["json"]["head"] == "repro/x" and captured["json"]["base"] in ("main", "master")
    assert "tok" in captured["headers"]["Authorization"]


def test_publish_without_token_returns_compare_url():
    ws = Workspace(FakeSandbox(), "/work/repo", "pytest")
    res = asyncio.run(publish(ws, _issue(), _repro(), FixResult("green", "d", 1, ""),
                              token=None, username=None))
    assert res.pushed is False and res.pr_url is None
    assert res.compare_url.startswith("https://github.com/o/c/compare/")
