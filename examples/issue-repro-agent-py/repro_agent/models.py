from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawIssue:
    title: str
    body: str
    comments: list[str] = field(default_factory=list)


@dataclass
class Issue:
    url: str
    title: str
    body: str
    repo_url: str
    owner: str
    repo: str
    repro_steps: list[str] = field(default_factory=list)
    repro_test: str | None = None
    expected: str = ""
    actual: str = ""


@dataclass
class CmdResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def combined(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


@dataclass
class ReproResult:
    test_path: str
    test_code: str
    reproduced: bool
    output: str


@dataclass
class FixResult:
    status: str  # "green" | "unresolved" | "skipped"
    diff: str
    attempts: int
    output: str


@dataclass
class PublishResult:
    branch: str
    pushed: bool
    pr_url: str | None
    compare_url: str
