from __future__ import annotations

import asyncio

from repro_agent.issue import scrape_issue, to_issue
from repro_agent.models import RawIssue
from tests.conftest import FakeBrowser, FakePage

URL = "https://github.com/tester/repro-agent-demo/issues/1"

_BODY = (
    "GET /widgets?limit=0 returns all widgets instead of none\n"
    "Expected\nAn empty list [] - a limit of zero means return zero rows.\n"
    "Actual\nAll five widgets are returned.\n"
    "Repro test\n"
)
_PY = (
    "def test_limit_zero_returns_empty():\n"
    "    from app import app\n"
    "    assert app.test_client().get('/widgets?limit=0').get_json() == []\n"
)


def test_to_issue_uses_python_code_block():
    raw = RawIssue(
        title="GET /widgets?limit=0 returns all widgets instead of none",
        body=_BODY,
        code_blocks=[{"lang": "shell", "code": "curl ..."}, {"lang": "python", "code": _PY}],
    )
    issue = to_issue(raw, URL, use_llm=False)
    assert issue.owner == "tester" and issue.repo == "repro-agent-demo"
    assert "test_limit_zero_returns_empty" in issue.repro_test
    assert issue.expected.lower().startswith("an empty list")
    assert "all five widgets" in issue.actual.lower()


def test_to_issue_falls_back_to_def_test_heuristic():
    raw = RawIssue(title="x", body="Expected\na\nActual\nb\n",
                   code_blocks=[{"lang": "", "code": "def test_foo():\n    assert 0\n"}])
    assert "def test_foo" in to_issue(raw, URL, use_llm=False).repro_test


def test_to_issue_no_block_dry_run_is_none():
    raw = RawIssue(title="x", body="Expected\na\nActual\nb\n", code_blocks=[])
    assert to_issue(raw, URL, use_llm=False).repro_test is None


def test_scrape_issue_reads_dom():
    page = FakePage(text="body text here", title="Bug title · Issue #1 · o/r",
                    blocks=[{"lang": "python", "code": "def test_x(): ..."}])
    raw = asyncio.run(scrape_issue(FakeBrowser(page), URL))
    assert raw.title == "Bug title"
    assert "body text here" in raw.body
    assert raw.code_blocks[0]["lang"] == "python"
