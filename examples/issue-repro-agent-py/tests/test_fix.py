from __future__ import annotations

import asyncio

from repro_agent.fix import apply_diff, run_fix
from repro_agent.models import Issue, ReproResult
from repro_agent.workspace import Workspace
from tests.conftest import FakeCmdResult, FakeSandbox

DIFF = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-if limit:\n+if limit is not None:\n"


def _issue():
    return Issue(url="u", title="t", body="b", repo_url="r", owner="o", repo="c",
                 expected="empty", actual="all")


def _repro():
    return ReproResult(test_path="/work/repo/tests/test_repro_1.py",
                       test_code="def test_x(): assert False",
                       reproduced=True,
                       output='File "/work/repo/app.py", line 10\nAssertionError')


def test_apply_diff_runs_git_apply():
    sbx = FakeSandbox(cmd_results={"git apply": FakeCmdResult(exitCode=0)})
    ws = Workspace(sbx, "/work/repo", "pytest")
    assert asyncio.run(apply_diff(ws, DIFF)) is True
    assert "/work/repo/.repro_agent.patch" in sbx.files.tree


def test_run_fix_skipped_in_dry_run():
    ws = Workspace(FakeSandbox(), "/work/repo", "pytest")
    res = asyncio.run(run_fix(ws, _issue(), _repro(), use_llm=False))
    assert res.status == "skipped" and res.attempts == 0


def test_run_fix_green_when_patch_fixes(monkeypatch):
    monkeypatch.setattr("repro_agent.fix.propose_patch", lambda **kw: DIFF)
    sbx = FakeSandbox(
        files={"/work/repo/app.py": "if limit:"},
        cmd_results={"git apply": FakeCmdResult(exitCode=0), "pytest": FakeCmdResult(exitCode=0)},
    )
    ws = Workspace(sbx, "/work/repo", "pytest")
    res = asyncio.run(run_fix(ws, _issue(), _repro(), use_llm=True, max_attempts=2))
    assert res.status == "green" and res.diff == DIFF and res.attempts == 1


def test_run_fix_unresolved_after_attempts(monkeypatch):
    monkeypatch.setattr("repro_agent.fix.propose_patch", lambda **kw: DIFF)
    sbx = FakeSandbox(
        files={"/work/repo/app.py": "if limit:"},
        cmd_results={"git apply": FakeCmdResult(exitCode=0),
                     "pytest": FakeCmdResult(exitCode=1, stdout="still red")},
    )
    ws = Workspace(sbx, "/work/repo", "pytest")
    res = asyncio.run(run_fix(ws, _issue(), _repro(), use_llm=True, max_attempts=2))
    assert res.status == "unresolved" and res.attempts == 2
