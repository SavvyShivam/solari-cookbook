"""Manual: verify the installed Solari SDK matches what the agent assumes.
Run with SOLARI_API_KEY set. Prints PASS lines; raises on a shape mismatch.
"""
from __future__ import annotations

import asyncio
import os


async def main() -> None:
    key = os.environ["SOLARI_API_KEY"]

    from solari_sandbox import SandboxClient

    async with SandboxClient(api_key=key, base_url="https://api.getsolari.com") as sandboxes:
        sbx = await sandboxes.create(template="base", timeout_ms=5 * 60_000)
        try:
            await sbx.connect()
            r = await sbx.commands.run("echo", args=["ok"])
            assert r.exitCode == 0 and "ok" in r.stdout, r
            await sbx.files.write("/tmp/x", "hi")
            assert (await sbx.files.read_text("/tmp/x")) == "hi"
            await sbx.git.clone("https://github.com/pallets/flask", path="/work/f", depth=1)
            st = await sbx.git.status(cwd="/work/f")
            assert st.branch and st.clean
            pv = await sbx.preview_url(8000)
            assert "url" in pv
            print("PASS: sandbox commands/files/git/preview_url shape matches")
        finally:
            await sbx.kill()

    from solari_browser import Solari

    async with Solari(api_key=key) as solari:
        async with await solari.launch(stealth=True) as browser:
            page = await browser.new_page()
            await page.goto("https://example.com", wait_until="domcontentloaded")
            assert "Example" in (await page.title())
            assert len(await page.content()) > 100
            print("PASS: browser launch/goto/title/content shape matches")


if __name__ == "__main__":
    asyncio.run(main())
