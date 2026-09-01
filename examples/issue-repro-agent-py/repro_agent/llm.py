from __future__ import annotations

import os
import re

from .models import Issue

# Provider is picked by which key is set. GROQ_API_KEY wins if both are present.
DEFAULT_MODEL = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-sonnet-5",
}
_DIFF_FENCE_RE = re.compile(r"```(?:diff|patch)?\n(.*?)```", re.DOTALL)
_DIFF_START_RE = re.compile(r"(^|\n)(--- |diff --git )")


class LLMUnavailable(RuntimeError):
    pass


def _provider() -> str | None:
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def llm_available() -> bool:
    return _provider() is not None


def extract_diff(text: str) -> str:
    """Pull a unified diff out of an LLM reply (fenced or bare). Raises ValueError
    if there is nothing diff-shaped."""
    for body in _DIFF_FENCE_RE.findall(text):
        if "---" in body or "diff --git" in body:
            return body.strip("\n")
    m = _DIFF_START_RE.search(text)
    if m:
        return text[m.start(2):].strip("\n")
    raise ValueError("no unified diff found in LLM reply")


def build_patch_prompt(issue: Issue, failing_test: str, traceback: str, files: dict[str, str]) -> str:
    file_blocks = "\n\n".join(f"### {path}\n```\n{src}\n```" for path, src in files.items())
    return (
        "You are fixing a bug in a Python project. Return ONLY a unified diff "
        "(git apply compatible, with a/ and b/ prefixes), no prose.\n\n"
        f"## Issue: {issue.title}\n{issue.body}\n\n"
        f"Expected: {issue.expected}\nActual: {issue.actual}\n\n"
        f"## Failing regression test\n```python\n{failing_test}\n```\n\n"
        f"## Test output / traceback\n```\n{traceback}\n```\n\n"
        f"## Source files\n{file_blocks or '(none extracted; infer from the traceback)'}\n\n"
        "Respond with the unified diff only."
    )


def build_repro_prompt(issue: Issue) -> str:
    return (
        "Write a single pytest test function that reproduces this bug and FAILS "
        "against the current code. Return ONLY a ```python code block.\n\n"
        f"## Issue: {issue.title}\n{issue.body}\n\n"
        f"Expected: {issue.expected}\nActual: {issue.actual}\n"
    )


def _model_for(provider: str, override: str | None) -> str:
    return override or os.environ.get("REPRO_AGENT_MODEL") or DEFAULT_MODEL[provider]


def _complete(prompt: str, model: str | None) -> str:
    provider = _provider()
    if provider is None:
        raise LLMUnavailable("no LLM key set (GROQ_API_KEY or ANTHROPIC_API_KEY)")
    chosen = _model_for(provider, model)
    messages = [{"role": "user", "content": prompt}]

    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(model=chosen, max_tokens=2000, messages=messages)
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    # groq — OpenAI-compatible chat completions
    import httpx

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        json={"model": chosen, "messages": messages, "max_tokens": 2000, "temperature": 0.2},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def propose_patch(*, issue: Issue, failing_test: str, traceback: str,
                  files: dict[str, str], model: str | None = None) -> str:
    return extract_diff(_complete(build_patch_prompt(issue, failing_test, traceback, files), model))


def propose_repro_test(*, issue: Issue, model: str | None = None) -> str:
    from .parsing import fenced_blocks

    reply = _complete(build_repro_prompt(issue), model)
    blocks = fenced_blocks(reply, "python") or fenced_blocks(reply)
    if not blocks:
        raise ValueError("LLM did not return a python code block")
    return blocks[0]
