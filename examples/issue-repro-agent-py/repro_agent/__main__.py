from __future__ import annotations

import argparse
import asyncio
import os
import sys

from .fix import run_fix
from .issue import scrape_issue, to_issue
from .publish import publish
from .report import publish_report, render_report_html
from .repro import run_repro
from .workspace import open_workspace


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="repro-agent", description="GitHub issue -> reproducing PR")
    p.add_argument("--issue-url", required=True)
    p.add_argument("--dry-run", action="store_true", help="skip the LLM; repro + report only")
    p.add_argument("--no-report", action="store_true")
    p.add_argument("--max-fix-attempts", type=int, default=2)
    p.add_argument("--out", default="report.png")
    return p.parse_args(argv)


def resolve_flags(args: argparse.Namespace, env: dict) -> dict:
    warnings: list[str] = []
    use_llm = not args.dry_run
    if use_llm and not env.get("ANTHROPIC_API_KEY"):
        warnings.append("ANTHROPIC_API_KEY not set — running as --dry-run (repro + report only)")
        use_llm = False
    token = env.get("GITHUB_TOKEN")
    username = env.get("GITHUB_USERNAME")
    if not token:
        warnings.append("GITHUB_TOKEN not set — will push nothing, print the compare URL")
    return {"use_llm": use_llm, "token": token, "username": username, "warnings": warnings}


async def run(args: argparse.Namespace, env: dict) -> int:
    from solari_browser import Solari
    from solari_sandbox import SandboxClient

    flags = resolve_flags(args, env)
    for w in flags["warnings"]:
        print(f"warning: {w}", file=sys.stderr)

    solari_key = env["SOLARI_API_KEY"]
    async with SandboxClient(api_key=solari_key, base_url="https://api.getsolari.com") as sandboxes:
        async with Solari(api_key=solari_key) as solari:
            async with await solari.launch(stealth=True) as browser:
                raw = await scrape_issue(browser, args.issue_url)
                try:
                    issue = to_issue(raw, args.issue_url, use_llm=flags["use_llm"])
                except ValueError as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    return 2

                ws = await open_workspace(sandboxes, issue.repo_url, token=flags["token"])
                try:
                    try:
                        repro = await run_repro(ws, issue, use_llm=flags["use_llm"])
                    except RuntimeError as exc:
                        print(f"error: {exc}", file=sys.stderr)
                        return 2
                    if not repro.reproduced:
                        print("could not reproduce: the repro test passed against the base commit",
                              file=sys.stderr)
                        return 3

                    fix = await run_fix(ws, issue, repro, use_llm=flags["use_llm"],
                                        max_attempts=args.max_fix_attempts)
                    await ws.sbx.commands.run(
                        "sh", args=["-c", f"rm -f {ws.repo_dir}/.repro_agent.patch"], cwd=ws.repo_dir
                    )
                    pub = await publish(ws, issue, repro, fix,
                                        token=flags["token"], username=flags["username"])

                    if not args.no_report:
                        html = render_report_html(issue, repro, fix, pub)
                        png = await publish_report(ws, browser, html, out_path=args.out)
                        print(f"report: {png}")

                    print(f"status: {fix.status}")
                    print(f"branch: {pub.branch}")
                    print(f"PR: {pub.pr_url}" if pub.pr_url else f"compare: {pub.compare_url}")
                    return 0
                finally:
                    await ws.sbx.kill()


def main() -> None:
    args = parse_args(sys.argv[1:])
    try:
        code = asyncio.run(run(args, dict(os.environ)))
    except Exception as exc:  # top-level guard: report and exit non-zero
        print(f"unexpected error: {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
