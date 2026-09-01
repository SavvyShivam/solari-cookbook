from __future__ import annotations

from .models import CmdResult

# Setup lines are run through `sh -c` (commands.run is not shell-interpreted).
_SETUP = {
    "pytest": ["python3 -m pip install -q -e . 2>/dev/null || python3 -m pip install -q -r requirements.txt 2>/dev/null || true"],
    "maven": ["mvn -q -DskipTests compile || true"],
    "npm": ["npm install --silent || true"],
}
_TEST_CMD = {
    "pytest": ["python3", "-m", "pytest", "-q"],
    "maven": ["mvn", "-q", "test"],
    "npm": ["npm", "test", "--silent"],
}


def detect_build_tool(names: list[str]) -> str:
    s = set(names)
    if "pom.xml" in s:
        return "maven"
    if "package.json" in s:
        return "npm"
    if {"pyproject.toml", "requirements.txt", "setup.py"} & s or "tests" in s:
        return "pytest"
    return "unknown"


async def _run(sbx, cmd: str, args: list[str], cwd: str) -> CmdResult:
    r = await sbx.commands.run(cmd, args=args, cwd=cwd)
    code = getattr(r, "exitCode", getattr(r, "exit_code", 0))
    return CmdResult(exit_code=code, stdout=getattr(r, "stdout", ""), stderr=getattr(r, "stderr", ""))


class Workspace:
    def __init__(self, sbx, repo_dir: str, build_tool: str):
        self.sbx = sbx
        self.repo_dir = repo_dir
        self.build_tool = build_tool

    async def run_tests(self, target: str | None = None) -> CmdResult:
        base = list(_TEST_CMD.get(self.build_tool, _TEST_CMD["pytest"]))
        if target and self.build_tool == "pytest":
            base.append(target)
        return await _run(self.sbx, base[0], base[1:], self.repo_dir)

    async def read_files(self, paths: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for p in paths:
            full = p if p.startswith("/") else f"{self.repo_dir}/{p}"
            try:
                out[p] = await self.sbx.files.read_text(full)
            except Exception:
                continue
        return out

    async def revert(self) -> None:
        await self.sbx.commands.run("git", args=["checkout", "--", "."], cwd=self.repo_dir)


async def open_workspace(sandboxes, repo_url: str, *, token: str | None = None,
                         repo_dir: str = "/work/repo") -> Workspace:
    sbx = await sandboxes.create(template="base", timeout_ms=15 * 60_000)
    await sbx.connect()
    await sbx.git.clone(repo_url, path=repo_dir, depth=1)
    listing = await sbx.files.list(repo_dir)
    names = [getattr(e, "name", e["name"] if isinstance(e, dict) else e) for e in listing]
    tool = detect_build_tool(names)
    for line in _SETUP.get(tool, []):
        await sbx.commands.run("sh", args=["-c", line], cwd=repo_dir)
    return Workspace(sbx, repo_dir, tool)
