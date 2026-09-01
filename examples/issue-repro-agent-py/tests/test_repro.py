from __future__ import annotations

import asyncio

import pytest

from repro_agent.models import Issue
from repro_agent.repro import run_repro
from repro_agent.workspace import Workspace
from tests.conftest import FakeCmdResult, FakeSandbox


def _ws(exit_code):
    sbx = FakeSandbox(cmd_results={"pytest": FakeCmdResult(exitCode=exit_code, stdout="boom")})
    return Workspace(sbx, "/work/repo", "pytest"), sbx


def _issue(test):
    return Issue(url="u", title="t", body="b", repo_url="r", owner="o", repo="c", repro_test=test)


def test_run_repro_writes_test_and_flags_reproduced():
    ws, sbx = _ws(exit_code=1)
    res = asyncio.run(run_repro(ws, _issue("def test_x():\n    assert False\n"), use_llm=False))
    assert res.reproduced is True
    assert "/work/repo/tests/test_repro_1.py" in sbx.files.tree
    assert "assert False" in sbx.files.tree["/work/repo/tests/test_repro_1.py"]


def test_run_repro_not_reproduced_when_test_passes():
    ws, _ = _ws(exit_code=0)
    res = asyncio.run(run_repro(ws, _issue("def test_x():\n    assert True\n"), use_llm=False))
    assert res.reproduced is False


def test_run_repro_raises_without_test_source():
    ws, _ = _ws(exit_code=1)
    with pytest.raises(RuntimeError):
        asyncio.run(run_repro(ws, _issue(None), use_llm=False))
