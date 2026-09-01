from __future__ import annotations

import asyncio

from repro_agent.fix import apply_edits, run_fix
from repro_agent.parsing import safe_repo_path
from repro_agent.models import Issue, ReproResult
from repro_agent.workspace import Workspace
from tests.conftest import FakeCmdResult, FakeSandbox

FIX = "from flask import Flask\n# fixed\nif limit is not None:\n    items = WIDGETS[:limit]\n"


def _issue():
    return Issue(url="u", title="t", body="b", repo_url="r", owner="o", repo="c",
                 expected="empty", actual="all")


def _repro():
    return ReproResult(test_path="/work/repo/tests/test_repro_1.py",
                       test_code="def test_x(): assert False",
                       reproduced=True,
                       output='File "/work/repo/app.py", line 10\nAssertionError')


def test_apply_edits_writes_sources_and_skips_tests():
    sbx = FakeSandbox()
    ws = Workspace(sbx, "/work/repo", "pytest")
    written = asyncio.run(apply_edits(ws, {"app.py": FIX, "tests/test_repro_1.py": "cheat"}))
    assert written == ["app.py"]
    assert sbx.files.tree["/work/repo/app.py"] == FIX
    assert "/work/repo/tests/test_repro_1.py" not in sbx.files.tree


def test_safe_repo_path_rejects_escapes_and_git():
    assert safe_repo_path("/work/repo", "pkg/app.py") == "/work/repo/pkg/app.py"
    assert safe_repo_path("/work/repo", "/etc/cron.d/x") is None
    assert safe_repo_path("/work/repo", "../../etc/passwd") is None
    assert safe_repo_path("/work/repo", "pkg/../../outside.py") is None
    assert safe_repo_path("/work/repo", ".git/hooks/pre-commit") is None
    assert safe_repo_path("/work/repo", "a/.git/config") is None


def test_apply_edits_refuses_paths_outside_the_clone():
    sbx = FakeSandbox()
    ws = Workspace(sbx, "/work/repo", "pytest")
    written = asyncio.run(apply_edits(ws, {
        "/etc/cron.d/pwn": "evil",
        "../../../root/.ssh/authorized_keys": "key",
        ".git/hooks/pre-commit": "#!/bin/sh\ncurl evil",
        "app.py": FIX,
    }))
    assert written == ["app.py"]
    assert sbx.files.tree == {"/work/repo/app.py": FIX}


def test_run_fix_skipped_in_dry_run():
    ws = Workspace(FakeSandbox(), "/work/repo", "pytest")
    res = asyncio.run(run_fix(ws, _issue(), _repro(), use_llm=False))
    assert res.status == "skipped" and res.attempts == 0


def test_run_fix_green_when_edit_fixes(monkeypatch):
    monkeypatch.setattr("repro_agent.fix.propose_file_edits", lambda **kw: {"app.py": FIX})
    sbx = FakeSandbox(
        files={"/work/repo/app.py": "if limit:"},
        cmd_results={"pytest": FakeCmdResult(exitCode=0), "git diff": FakeCmdResult(stdout="D")},
    )
    ws = Workspace(sbx, "/work/repo", "pytest")
    res = asyncio.run(run_fix(ws, _issue(), _repro(), use_llm=True, max_attempts=2))
    assert res.status == "green" and res.attempts == 1 and res.diff == "D"


def test_run_fix_unresolved_after_attempts(monkeypatch):
    monkeypatch.setattr("repro_agent.fix.propose_file_edits", lambda **kw: {"app.py": FIX})
    sbx = FakeSandbox(
        files={"/work/repo/app.py": "if limit:"},
        cmd_results={"pytest": FakeCmdResult(exitCode=1, stdout="still red")},
    )
    ws = Workspace(sbx, "/work/repo", "pytest")
    res = asyncio.run(run_fix(ws, _issue(), _repro(), use_llm=True, max_attempts=2))
    assert res.status == "unresolved" and res.attempts == 2


def test_run_fix_unresolved_when_only_test_edits(monkeypatch):
    monkeypatch.setattr("repro_agent.fix.propose_file_edits",
                        lambda **kw: {"tests/test_repro_1.py": "assert True"})
    sbx = FakeSandbox(files={"/work/repo/app.py": "if limit:"})
    ws = Workspace(sbx, "/work/repo", "pytest")
    res = asyncio.run(run_fix(ws, _issue(), _repro(), use_llm=True, max_attempts=1))
    assert res.status == "unresolved"
