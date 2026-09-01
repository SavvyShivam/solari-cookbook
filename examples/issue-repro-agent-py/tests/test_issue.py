from __future__ import annotations

import asyncio
import pathlib

from repro_agent.issue import scrape_issue, to_issue
from repro_agent.models import RawIssue
from tests.conftest import FakeBrowser, FakePage

FIXT = pathlib.Path(__file__).parent / "fixtures"
URL = "https://github.com/tester/repro-agent-demo/issues/1"


def test_to_issue_dry_run_uses_python_block():
    body = (FIXT / "issue_body.md").read_text()
    raw = RawIssue(title="GET /widgets?limit=0 returns all widgets instead of none", body=body)
    issue = to_issue(raw, URL, use_llm=False)
    assert issue.owner == "tester" and issue.repo == "repro-agent-demo"
    assert issue.repo_url == "https://github.com/tester/repro-agent-demo"
    assert "test_limit_zero_returns_empty" in issue.repro_test
    assert issue.expected.lower().startswith("an empty list")
    assert "all five widgets" in issue.actual.lower()


def test_to_issue_no_python_block_dry_run_is_none():
    raw = RawIssue(title="x", body="## Expected\n\na\n\n## Actual\n\nb\n")
    issue = to_issue(raw, URL, use_llm=False)
    assert issue.repro_test is None


def test_scrape_issue_reads_page_text():
    page = FakePage(text="<h1>Bug title</h1><div>body text here</div>", title="Bug title · Issue #1")
    raw = asyncio.run(scrape_issue(FakeBrowser(page), URL))
    assert isinstance(raw, RawIssue)
    assert "body text here" in raw.body
    assert raw.title == "Bug title"
