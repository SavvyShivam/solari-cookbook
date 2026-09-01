from __future__ import annotations

import asyncio
import html as _html
from pathlib import Path

from .models import FixResult, Issue, PublishResult, ReproResult

_CSS = """
body{font:14px/1.5 -apple-system,system-ui,sans-serif;max-width:820px;margin:40px auto;padding:0 16px;color:#1a1a1a}
h1{font-size:20px} .tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600}
.red{background:#ffe0e0;color:#a10000} .green{background:#e0ffe4;color:#0a7a1a}
pre{background:#0d1117;color:#e6edf3;padding:12px;border-radius:6px;overflow-x:auto;font-size:12px}
a{color:#0969da}
"""


def _pre(text: str) -> str:
    return f"<pre>{_html.escape(text)}</pre>"


def _a(url: str, label: str | None = None) -> str:
    u = _html.escape(url, quote=True)
    return f'<a href="{u}">{_html.escape(label or url)}</a>'


def render_report_html(issue: Issue, repro: ReproResult, fix: FixResult,
                       publish: PublishResult) -> str:
    status = ('<span class="tag green">FIX GREEN</span>' if fix.status == "green"
              else '<span class="tag red">REPRODUCED; FIX UNRESOLVED</span>')
    pr_line = (
        f"<p>PR: {_a(publish.pr_url)}</p>" if publish.pr_url
        else f'<p>Branch pushed: <code>{_html.escape(publish.branch)}</code> — '
             f'{_a(publish.compare_url, "open a PR")}</p>'
    )
    fix_block = (f"<h2>Fix diff</h2>{_pre(fix.diff)}" if fix.status == "green"
                 else "<h2>Fix</h2><p>Not resolved automatically; regression test committed.</p>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Repro Agent — {_html.escape(issue.title)}</title><style>{_CSS}</style></head><body>
<h1>{_html.escape(issue.title)} {status}</h1>
<p>Issue: {_a(issue.url)}</p>
{pr_line}
<h2>Reproducing test</h2>{_pre(repro.test_code)}
<h2>Captured failure (base commit)</h2>{_pre(repro.output[:4000])}
{fix_block}
</body></html>"""


async def publish_report(ws, browser, html: str, *, out_path: str = "report.png") -> str:
    """Serve the report from the sandbox and screenshot it with the Solari browser."""
    await ws.sbx.files.write(f"{ws.repo_dir}/report.html", html)
    proc = await ws.sbx.commands.start(
        "python3", args=["-m", "http.server", "8000"], cwd=ws.repo_dir
    )
    try:
        await asyncio.sleep(1)
        preview = await ws.sbx.preview_url(8000)
        # preview url is "https://host?pt_token=..." — the token is auth, keep it.
        base = preview["url"]
        if "?" in base:
            host, query = base.split("?", 1)
            target = f"{host.rstrip('/')}/report.html?{query}"
        else:
            target = f"{base.rstrip('/')}/report.html"
        page = await browser.new_page()
        await page.goto(target, wait_until="domcontentloaded")
        await page.screenshot(full_page=True, path=out_path)
    finally:
        await proc.kill()
    return out_path
