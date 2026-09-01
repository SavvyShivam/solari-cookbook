from __future__ import annotations

from repro_agent.__main__ import parse_args, resolve_flags


def test_parse_args_defaults():
    a = parse_args(["--issue-url", "https://github.com/o/c/issues/1"])
    assert a.issue_url.endswith("/issues/1")
    assert a.dry_run is False and a.max_fix_attempts == 2


def test_resolve_flags_dry_run_forces_no_llm():
    a = parse_args(["--issue-url", "u", "--dry-run"])
    flags = resolve_flags(a, {"ANTHROPIC_API_KEY": "x"})
    assert flags["use_llm"] is False


def test_resolve_flags_missing_anthropic_warns_and_disables_llm():
    a = parse_args(["--issue-url", "u"])
    flags = resolve_flags(a, {})
    assert flags["use_llm"] is False
    assert any("ANTHROPIC_API_KEY" in w for w in flags["warnings"])


def test_resolve_flags_happy_path():
    a = parse_args(["--issue-url", "u"])
    flags = resolve_flags(a, {"ANTHROPIC_API_KEY": "x", "GITHUB_TOKEN": "t", "GITHUB_USERNAME": "me"})
    assert flags["use_llm"] is True and flags["token"] == "t" and flags["username"] == "me"
