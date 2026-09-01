from __future__ import annotations

import asyncio

from repro_agent.models import FixResult, Issue, PublishResult, ReproResult
from repro_agent.report import publish_report, render_report_html
from repro_agent.workspace import Workspace
from tests.conftest import FakeBrowser, FakePage, FakeSandbox


def _args():
    issue = Issue(url="u", title="limit=0 bug", body="b", repo_url="r", owner="o", repo="c")
    repro = ReproResult("/work/repo/tests/test_repro_1.py", "def test_x(): ...", True, "AssertionError")
    fix = FixResult("green", "--- a\n+++ b\n", 1, "ok")
    pub = PublishResult("repro/limit-0-bug", True, "https://github.com/o/c/pull/9", "cmp")
    return issue, repro, fix, pub


def test_render_report_html_contains_key_facts():
    html = render_report_html(*_args())
    assert "<html" in html.lower()
    assert "limit=0 bug" in html
    assert "pull/9" in html
    assert "AssertionError" in html


def test_publish_report_screenshots_and_writes(tmp_path):
    ws = Workspace(FakeSandbox(), "/work/repo", "pytest")
    out = tmp_path / "r.png"
    path = asyncio.run(publish_report(ws, FakeBrowser(FakePage()), "<html>hi</html>", out_path=str(out)))
    assert path == str(out)
    assert out.read_bytes().startswith(b"\x89PNG")
    assert "/work/repo/report.html" in ws.sbx.files.tree
