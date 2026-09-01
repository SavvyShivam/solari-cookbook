from __future__ import annotations

from .models import Issue, ReproResult
from .workspace import Workspace


async def run_repro(ws: Workspace, issue: Issue, *, use_llm: bool, n: int = 1) -> ReproResult:
    """Write the reproducing test into the repo and run it. `reproduced` is True
    when the test fails (exit != 0), i.e. the bug is present."""
    test_code = issue.repro_test
    if not test_code and use_llm:
        from .llm import propose_repro_test

        test_code = propose_repro_test(issue=issue)
    if not test_code:
        raise RuntimeError(
            "no repro test: the issue has no ```python block and --dry-run disables the LLM"
        )
    test_path = f"{ws.repo_dir}/tests/test_repro_{n}.py"
    await ws.sbx.files.write(test_path, test_code if test_code.endswith("\n") else test_code + "\n")
    result = await ws.run_tests(test_path)
    return ReproResult(
        test_path=test_path,
        test_code=test_code,
        reproduced=result.exit_code != 0,
        output=result.combined,
    )
