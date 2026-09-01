from __future__ import annotations

import re

from .models import Issue, RawIssue
from .parsing import fenced_blocks, repo_ref_from_issue_url, section_after

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub("\n", html)
    return _WS_RE.sub("\n\n", text).strip()


async def scrape_issue(browser, url: str) -> RawIssue:
    """Open the issue in the Solari browser and pull its text out of the DOM."""
    page = await browser.new_page()
    await page.goto(url, wait_until="domcontentloaded")
    title = (await page.title()).split("·")[0].strip()
    body = _strip_html(await page.content())
    return RawIssue(title=title, body=body)


def to_issue(raw: RawIssue, url: str, *, use_llm: bool) -> Issue:
    """Build a structured Issue. `repro_test` = first ```python block in the body,
    else the LLM writes one (when use_llm), else None (dry-run)."""
    repo_url, owner, repo = repo_ref_from_issue_url(url)
    steps = fenced_blocks(raw.body)
    py = fenced_blocks(raw.body, "python")
    repro_test = py[0] if py else None
    expected = section_after(raw.body, "expected")
    actual = section_after(raw.body, "actual")
    if repro_test is None and use_llm:
        from .llm import propose_repro_test

        stub = Issue(url=url, title=raw.title, body=raw.body, repo_url=repo_url,
                     owner=owner, repo=repo, expected=expected, actual=actual)
        repro_test = propose_repro_test(issue=stub)
    return Issue(
        url=url, title=raw.title, body=raw.body, repo_url=repo_url, owner=owner, repo=repo,
        repro_steps=steps, repro_test=repro_test, expected=expected, actual=actual,
    )
