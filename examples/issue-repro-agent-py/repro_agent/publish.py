from __future__ import annotations

from urllib.parse import quote

from .models import FixResult, Issue, PublishResult, ReproResult
from .parsing import slugify

_AUTHOR = "Repro Agent"
_EMAIL = "repro-agent@users.noreply.github.com"


async def _push_branch(ws, issue: Issue, branch: str, username: str, token: str) -> None:
    """Force-push the agent's branch. `repro/*` branches are agent-owned, so a
    re-run replaces the prior attempt rather than failing on non-fast-forward.
    Credentials are spliced into an `insteadOf` rewrite for this one git process
    (the same technique the SDK's git.push uses) so they never land in config."""
    plain = issue.repo_url
    authed = plain.replace(
        "https://", f"https://{quote(username, safe='')}:{quote(token, safe='')}@", 1
    )
    r = await ws.sbx.commands.run(
        "git",
        args=["-c", f"url.{authed}.insteadOf={plain}", "push", "-f", "origin", f"HEAD:{branch}"],
        cwd=ws.repo_dir,
    )
    if getattr(r, "exitCode", getattr(r, "exit_code", 1)) != 0:
        raise RuntimeError(f"git push failed: {getattr(r, 'stderr', '')[:400]}")


def pr_title(issue: Issue, fix: FixResult) -> str:
    suffix = "" if fix.status == "green" else " [reproduced; fix unresolved]"
    return f"Reproduce: {issue.title}{suffix}"


def pr_body(issue: Issue, repro: ReproResult, fix: FixResult) -> str:
    if fix.status == "green":
        fix_section = (
            f"### Fix (tests green in {fix.attempts} attempt(s))\n```diff\n{fix.diff}\n```"
        )
    else:
        fix_section = (
            "### Fix\nNot resolved automatically. This PR adds the failing regression "
            "test only; a human should take the fix from here."
        )
    return (
        "Automated by the Solari Issue Repro Agent.\n\n"
        f"Closes {issue.url}\n\n"
        f"### Reproduction\nAdded `{repro.test_path.split('/')[-1]}`:\n"
        f"```python\n{repro.test_code}\n```\n\n"
        f"Captured failing against the base commit:\n```\n{repro.output[:1500]}\n```\n\n"
        f"{fix_section}\n"
    )


async def open_pr(issue: Issue, branch: str, title: str, body: str, token: str, *, http=None) -> str:
    """POST a PR to GitHub. Tries base `main` then `master`. Returns the html_url."""
    owns_client = http is None
    if owns_client:
        import httpx

        http = httpx.AsyncClient(timeout=30)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    api = f"https://api.github.com/repos/{issue.owner}/{issue.repo}"
    try:
        resp = None
        for base in ("main", "master"):
            resp = await http.post(
                f"{api}/pulls",
                headers=headers,
                json={"title": title, "body": body, "head": branch, "base": base},
            )
            if resp.status_code == 201:
                return resp.json()["html_url"]
            if resp.status_code == 422 and "already exist" in resp.text.lower():
                existing = await http.get(
                    f"{api}/pulls", headers=headers,
                    params={"head": f"{issue.owner}:{branch}", "state": "open"},
                )
                items = existing.json()
                if items:
                    return items[0]["html_url"]
        raise RuntimeError(
            f"PR creation failed: {resp.status_code if resp else '?'} "
            f"{resp.json() if resp else ''}"
        )
    finally:
        if owns_client:
            await http.aclose()


async def publish(ws, issue: Issue, repro: ReproResult, fix: FixResult, *,
                  token: str | None, username: str | None) -> PublishResult:
    branch = f"repro/{slugify(issue.title)}"
    await ws.sbx.git.checkout(branch, cwd=ws.repo_dir, create=True)
    # Stage tracked edits + the new repro test only — never the build artifacts
    # (`*.egg-info`, `.pytest_cache`, ...) that setup/pytest leave behind.
    await ws.sbx.commands.run("git", args=["add", "-u"], cwd=ws.repo_dir)
    await ws.sbx.git.add([repro.test_path], ws.repo_dir)
    await ws.sbx.git.commit(pr_title(issue, fix), cwd=ws.repo_dir, author=_AUTHOR, email=_EMAIL)
    compare_url = f"{issue.repo_url}/compare/{branch}?expand=1"
    if not token or not username:
        return PublishResult(branch=branch, pushed=False, pr_url=None, compare_url=compare_url)
    await _push_branch(ws, issue, branch, username, token)
    pr_url = await open_pr(issue, branch, pr_title(issue, fix), pr_body(issue, repro, fix), token)
    return PublishResult(branch=branch, pushed=True, pr_url=pr_url, compare_url=compare_url)
