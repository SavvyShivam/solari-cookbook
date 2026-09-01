from __future__ import annotations

from .llm import LLMUnavailable, propose_file_edits
from .models import FixResult, Issue, ReproResult
from .parsing import files_in_traceback
from .workspace import Workspace


def _is_test_path(path: str) -> bool:
    tail = path.replace("\\", "/").split("/")[-1]
    return "/tests/" in f"/{path}/" or tail.startswith("test_") or tail == "conftest.py"


async def _repo_sources(ws: Workspace, limit: int = 12) -> list[str]:
    """Repo-relative paths of non-test Python files, shallowest first."""
    r = await ws.sbx.commands.run(
        "sh",
        args=["-c",
              "find . -name '*.py' -not -path './tests/*' -not -path './.git/*' "
              "-not -name 'test_*' | sed 's|^\\./||' | head -40"],
        cwd=ws.repo_dir,
    )
    files = [ln.strip() for ln in getattr(r, "stdout", "").splitlines() if ln.strip()]
    files.sort(key=lambda p: p.count("/"))
    return files[:limit]


async def _git_diff(ws: Workspace) -> str:
    r = await ws.sbx.commands.run("git", args=["diff"], cwd=ws.repo_dir)
    return getattr(r, "stdout", "")


async def apply_edits(ws: Workspace, edits: dict[str, str]) -> list[str]:
    """Write each non-test file edit into the repo. Returns the paths written."""
    written = []
    for path, content in edits.items():
        if _is_test_path(path):
            continue
        full = path if path.startswith("/") else f"{ws.repo_dir}/{path}"
        await ws.sbx.files.write(full, content)
        written.append(path)
    return written


async def run_fix(ws: Workspace, issue: Issue, repro: ReproResult, *, use_llm: bool,
                  max_attempts: int = 2, model: str | None = None) -> FixResult:
    if not use_llm:
        return FixResult(status="skipped", diff="", attempts=0, output="LLM disabled (--dry-run)")

    # An assertion failure's traceback names only the test file, so seed context
    # with the repo's own (non-test) Python files too.
    src = await _repo_sources(ws)

    last_output = repro.output
    for attempt in range(1, max_attempts + 1):
        paths = list(dict.fromkeys(files_in_traceback(last_output) + src))
        context = {p: c for p, c in (await ws.read_files(paths)).items() if not _is_test_path(p)}
        try:
            edits = propose_file_edits(
                issue=issue, failing_test=repro.test_code,
                traceback=last_output, files=context, model=model,
            )
        except (LLMUnavailable, ValueError) as exc:
            return FixResult(status="unresolved", diff="", attempts=attempt, output=str(exc))

        if not await apply_edits(ws, edits):
            last_output = "LLM proposed no editable (non-test) file changes"
            continue

        result = await ws.run_tests(repro.test_path)
        if result.exit_code == 0:
            return FixResult(status="green", diff=await _git_diff(ws),
                             attempts=attempt, output=result.combined)
        last_output = result.combined
        await ws.revert()

    return FixResult(status="unresolved", diff="", attempts=max_attempts, output=last_output)
