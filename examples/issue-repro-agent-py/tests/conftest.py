"""Hand-rolled fakes mirroring the real solari-sandbox / solari-browser shapes
(verified by introspection: CommandResult.exitCode, FsEntry.name/.dir/.size,
commands.run keyword-only args, preview_url -> dict, no `async with` on Sandbox).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeCmdResult:
    exitCode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class FakeFsEntry:
    name: str
    dir: bool = False
    size: int = 0


class FakeProc:
    async def kill(self, signal=None):
        return None

    def on_data(self, cb):
        return None

    async def wait(self):
        return 0


class FakeCommands:
    def __init__(self, results: dict[str, FakeCmdResult] | None = None):
        self.results = results or {}
        self.calls: list[tuple[str, list[str]]] = []

    async def run(self, cmd, *, args=None, cwd=None, env=None, user=None,
                  timeout_ms=None, background=False, on_stdout=None, on_stderr=None):
        args = args or []
        self.calls.append((cmd, list(args)))
        key = " ".join([cmd, *args])
        for pat, res in self.results.items():
            if pat in key:
                return res
        return FakeCmdResult()

    async def start(self, cmd, *, args=None, cwd=None, env=None, user=None,
                    on_stdout=None, on_stderr=None):
        self.calls.append((cmd, list(args or [])))
        return FakeProc()


class FakeGit:
    def __init__(self):
        self.calls: list[tuple] = []

    async def clone(self, url, *, path=None, branch=None, depth=None,
                    username=None, password=None, cwd=None):
        self.calls.append(("clone", url, path))

    async def checkout(self, ref, *, cwd=None, create=False):
        self.calls.append(("checkout", ref, create))

    async def add(self, paths, cwd=None):
        self.calls.append(("add", tuple(paths)))

    async def commit(self, message, *, cwd=None, author=None, email=None, all=False):
        self.calls.append(("commit", message))
        return {"hash": "deadbeefcafe"}

    async def push(self, *, cwd=None, remote=None, branch=None, username=None, password=None):
        self.calls.append(("push", branch, username, bool(password)))


class FakeFiles:
    def __init__(self, tree: dict[str, str] | None = None):
        self.tree = dict(tree or {})

    async def write(self, path, data, mode=None):
        self.tree[path] = data

    async def read_text(self, path):
        return self.tree[path]

    async def read(self, path):
        return self.tree[path].encode()

    async def list(self, path):
        prefix = path.rstrip("/") + "/"
        seen: dict[str, bool] = {}
        for p in self.tree:
            if p.startswith(prefix):
                rest = p[len(prefix):]
                head = rest.split("/")[0]
                seen[head] = "/" in rest
        return [FakeFsEntry(name=n, dir=d) for n, d in sorted(seen.items())]


class FakeSandbox:
    def __init__(self, *, files=None, cmd_results=None, snapshot_id="snap_1"):
        self.files = FakeFiles(files)
        self.commands = FakeCommands(cmd_results)
        self.git = FakeGit()
        self.killed = False
        self.sandboxId = "sbx_fake"
        self.id = "sbx_fake"
        self._snapshot_id = snapshot_id

    async def connect(self):
        return None

    async def preview_url(self, port):
        return {"url": f"https://preview.example/{port}", "token": "pt_fake"}

    async def snapshot(self, name=None):
        return self._snapshot_id

    async def kill(self):
        self.killed = True

    async def close(self):
        self.killed = True


class FakeSandboxClient:
    """Pops sandboxes from a queue per create() so parallel tests can hand out
    distinct instances; falls back to a single sandbox forever."""

    def __init__(self, sandbox=None, queue=None):
        self._single = sandbox
        self._queue = list(queue or [])

    async def create(self, *, template=None, from_snapshot=None, timeout_ms=None, **kw):
        if self._queue:
            return self._queue.pop(0)
        return self._single

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakePage:
    def __init__(self, text: str = "", title: str = "", blocks=None):
        self._text = text
        self._title = title
        self._blocks = blocks or []
        self.goto_calls: list[str] = []

    async def goto(self, url, wait_until=None):
        self.goto_calls.append(url)

    async def wait_for_selector(self, selector, timeout=None):
        return None

    async def title(self):
        return self._title

    async def content(self):
        return self._text

    async def evaluate(self, expression):
        return {"text": self._text, "blocks": self._blocks}

    async def screenshot(self, full_page=False, path=None):
        data = b"\x89PNG\r\n\x1a\n" + b"fake"
        if path:
            from pathlib import Path

            Path(path).write_bytes(data)
        return data


class FakeBrowser:
    def __init__(self, page: FakePage):
        self._page = page
        self.id = "browser_fake"

    async def new_page(self):
        return self._page
