"""Local self-check of the planted bug the agent is built to reproduce.

Mirrors `repro-agent-demo/app.py`'s `/widgets?limit=0` handler both ways so the
fixture stays a valid target. No Solari, no network. Run: `python demo.py`.
"""
from __future__ import annotations

WIDGETS = [{"id": i} for i in range(1, 6)]


def list_widgets(limit, *, fixed: bool):
    guard = (limit is not None) if fixed else bool(limit)
    return WIDGETS[:limit] if guard else WIDGETS


if __name__ == "__main__":
    assert list_widgets(0, fixed=False) == WIDGETS, "buggy handler returns all rows for limit=0"
    assert list_widgets(0, fixed=True) == [], "fixed handler returns [] for limit=0"
    assert list_widgets(2, fixed=True) == WIDGETS[:2], "fixed handler still honours a real limit"
    assert list_widgets(None, fixed=True) == WIDGETS, "no limit -> all rows"
    print("OK: planted bug reproduces, fix resolves it, real limits still work")
