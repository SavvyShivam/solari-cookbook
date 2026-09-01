from __future__ import annotations

from .models import Issue, RawIssue
from .parsing import fenced_blocks, repo_ref_from_issue_url, section_after

# Runs in the page. GitHub renders a ```lang block as
# <div class="highlight highlight-source-LANG" data-snippet-clipboard-copy-content="RAW">,
# so the language and the exact source both survive in the DOM.
_EXTRACT_JS = r"""() => {
  const body = document.querySelector('.markdown-body') || document.body;
  const blocks = [...document.querySelectorAll('.markdown-body .highlight, .markdown-body pre')]
    .map(el => ({
      lang: (el.className.match(/highlight-source-([\w-]+)/) || [null, ''])[1],
      code: el.getAttribute('data-snippet-clipboard-copy-content') || el.innerText || '',
    }))
    .filter(b => b.code.trim());
  return { text: body.innerText || '', blocks };
}"""


async def scrape_issue(browser, url: str) -> RawIssue:
    """Open the issue in the Solari browser and pull its text + code blocks out of
    the rendered DOM."""
    page = await browser.new_page()
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".markdown-body", timeout=15000)
    except Exception:
        pass
    data = await page.evaluate(_EXTRACT_JS)
    title = (await page.title()).split("·")[0].strip()
    blocks = data.get("blocks") or []
    return RawIssue(title=title, body=data.get("text", ""), code_blocks=blocks)


def to_issue(raw: RawIssue, url: str, *, use_llm: bool) -> Issue:
    """Build a structured Issue. `repro_test` = first python code block in the
    issue, else the LLM writes one (when use_llm), else None (dry-run)."""
    repo_url, owner, repo = repo_ref_from_issue_url(url)

    blocks = list(raw.code_blocks) or [
        {"lang": "", "code": c} for c in fenced_blocks(raw.body)
    ]
    steps = [b["code"] for b in blocks]
    py = [b["code"] for b in blocks if (b.get("lang") or "").lower() in ("python", "py")]
    if not py:  # heuristic: a block that looks like a pytest function
        py = [c for c in steps if "def test" in c]
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
