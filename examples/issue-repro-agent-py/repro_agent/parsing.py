from __future__ import annotations

import re

_ISSUE_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/issues/\d+")
_FENCE_RE = re.compile(r"```([\w-]*)\n(.*?)```", re.DOTALL)
_TB_FILE_RE = re.compile(r'File "([^"]+)"')
_TB_REL_RE = re.compile(r"\b([\w./-]+\.py):\d+")
_EXCLUDE = ("site-packages", "/usr/lib/python", "/usr/local/lib/python", "dist-packages")


def repo_ref_from_issue_url(url: str) -> tuple[str, str, str]:
    """(repo_url, owner, repo) from a GitHub issue URL. Raises ValueError otherwise."""
    m = _ISSUE_RE.search(url)
    if not m:
        raise ValueError(f"not a GitHub issue URL: {url}")
    owner, repo = m.group(1), m.group(2)
    return f"https://github.com/{owner}/{repo}", owner, repo


def fenced_blocks(markdown: str, lang: str | None = None) -> list[str]:
    """Contents of ``` fences, optionally filtered by the language tag."""
    out = []
    for tag, body in _FENCE_RE.findall(markdown):
        if lang is None or tag.lower() == lang.lower():
            out.append(body.strip("\n"))
    return out


def _norm_heading(line: str) -> str:
    return line.strip().lstrip("#").strip().strip("*").strip().rstrip(":").strip()


def _looks_like_heading(line: str) -> bool:
    """A markdown heading, or a rendered-DOM bare heading: a short, capitalised
    line with no sentence punctuation (GitHub innerText drops the `#`)."""
    s = line.strip()
    if not s:
        return False
    if s.lstrip().startswith("#"):
        return True
    if s.startswith("**") and s.endswith("**") and len(s) > 4:
        return True
    words = s.split()
    return (
        len(words) <= 5
        and s[0].isupper()
        and not s.endswith((".", "!", "?", ",", ";", ")", "`"))
    )


def section_after(markdown: str, heading: str) -> str:
    """Text between a heading matching `heading` (case-insensitive; markdown
    `#`/`**` or a rendered-DOM bare line) and the next heading."""
    want = heading.strip().lower()
    collecting = False
    buf: list[str] = []
    for line in markdown.splitlines():
        if _looks_like_heading(line):
            if collecting:
                break
            if _norm_heading(line).lower() == want:
                collecting = True
            continue
        if collecting and line.strip():
            buf.append(line)
    return "\n".join(buf).strip()


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-")


def files_in_traceback(text: str) -> list[str]:
    """De-duplicated repo-relative / absolute source paths from a traceback,
    excluding stdlib and site-packages."""
    hits: list[str] = []
    for path in _TB_FILE_RE.findall(text) + _TB_REL_RE.findall(text):
        if any(x in path for x in _EXCLUDE):
            continue
        if path not in hits:
            hits.append(path)
    return hits
