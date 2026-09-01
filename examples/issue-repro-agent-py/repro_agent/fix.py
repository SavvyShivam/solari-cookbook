from __future__ import annotations

from .llm import LLMUnavailable, propose_patch
from .models import FixResult, Issue, ReproResult
from .parsing import files_in_traceback
from .workspace import Workspace

_PATCH_NAME = ".repro_agent.patch"


async def apply_diff(ws: Workspace, diff: str) -> bool:
    """Write the diff into the repo and `git apply` it. Returns whether it applied."""
    await ws.sbx.files.write(
        f"{ws.repo_dir}/{_PATCH_NAME}", diff if diff.endswith("\n") else diff + "\n"
    )
    r = await ws.sbx.commands.run(
        "git", args=["apply", "--recount", _PATCH_NAME], cwd=ws.repo_dir
    )
    return getattr(r, "exitCode", getattr(r, "exit_code", 0)) == 0


async def run_fix(ws: Workspace, issue: Issue, repro: ReproResult, *, use_llm: bool,
                  max_attempts: int = 2, model: str | None = None) -> FixResult:
    if not use_llm:
        return FixResult(status="skipped", diff="", attempts=0, output="LLM disabled (--dry-run)")

    last_output = repro.output
    for attempt in range(1, max_attempts + 1):
        context = await ws.read_files(files_in_traceback(last_output))
        try:
            diff = propose_patch(
                issue=issue, failing_test=repro.test_code,
                traceback=last_output, files=context, model=model,
            )
        except (LLMUnavailable, ValueError) as exc:
            return FixResult(status="unresolved", diff="", attempts=attempt, output=str(exc))

        if not await apply_diff(ws, diff):
            last_output = "patch did not apply cleanly"
            await ws.revert()
            continue

        result = await ws.run_tests(repro.test_path)
        if result.exit_code == 0:
            return FixResult(status="green", diff=diff, attempts=attempt, output=result.combined)
        last_output = result.combined
        await ws.revert()

    return FixResult(status="unresolved", diff="", attempts=max_attempts, output=last_output)
