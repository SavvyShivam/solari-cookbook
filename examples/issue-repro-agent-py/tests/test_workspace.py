from __future__ import annotations

import asyncio

from repro_agent.workspace import Workspace, detect_build_tool, open_workspace
from tests.conftest import FakeCmdResult, FakeSandbox, FakeSandboxClient


def test_detect_build_tool():
    assert detect_build_tool(["app.py", "requirements.txt", "tests"]) == "pytest"
    assert detect_build_tool(["pom.xml", "src"]) == "maven"
    assert detect_build_tool(["package.json"]) == "npm"
    assert detect_build_tool(["README.md"]) == "unknown"


def test_open_workspace_clones_and_detects():
    sbx = FakeSandbox(files={"/work/repo/requirements.txt": "flask", "/work/repo/tests/t.py": ""})
    ws = asyncio.run(open_workspace(FakeSandboxClient(sbx), "https://github.com/o/c"))
    assert ws.build_tool == "pytest"
    assert ("clone", "https://github.com/o/c", "/work/repo") in sbx.git.calls


def test_run_tests_pytest_invocation():
    sbx = FakeSandbox(
        files={"/work/repo/requirements.txt": ""},
        cmd_results={"pytest": FakeCmdResult(exitCode=1, stdout="1 failed")},
    )
    ws = asyncio.run(open_workspace(FakeSandboxClient(sbx), "https://github.com/o/c"))
    res = asyncio.run(ws.run_tests("/work/repo/tests/test_repro_1.py"))
    assert res.exit_code == 1 and "failed" in res.stdout
    assert any("pytest" in " ".join(c[1]) for c in sbx.commands.calls)
