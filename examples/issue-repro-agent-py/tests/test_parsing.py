from __future__ import annotations

import pytest

from repro_agent.parsing import (
    fenced_blocks,
    files_in_traceback,
    repo_ref_from_issue_url,
    section_after,
    slugify,
)


def test_repo_ref_from_issue_url():
    assert repo_ref_from_issue_url("https://github.com/octo/cat/issues/12") == (
        "https://github.com/octo/cat", "octo", "cat",
    )


def test_repo_ref_rejects_non_issue():
    with pytest.raises(ValueError):
        repo_ref_from_issue_url("https://github.com/octo/cat")


def test_fenced_blocks_filter_by_lang():
    md = "text\n```python\nx = 1\n```\nmore\n```bash\nls\n```\n"
    assert fenced_blocks(md, "python") == ["x = 1"]
    assert len(fenced_blocks(md)) == 2


def test_section_after():
    md = "## Expected\n\nempty list\n\n## Actual\n\nall rows\n"
    assert section_after(md, "expected").strip() == "empty list"


def test_slugify():
    assert slugify("GET /widgets?limit=0 returns all!") == "get-widgets-limit-0-returns-all"


def test_files_in_traceback_excludes_site_packages():
    tb = (
        'File "/work/repo/app.py", line 10, in list_widgets\n'
        'File "/usr/lib/python3.11/json/__init__.py", line 1\n'
        "tests/test_repro_1.py:5: AssertionError\n"
    )
    assert files_in_traceback(tb) == ["/work/repo/app.py", "tests/test_repro_1.py"]
