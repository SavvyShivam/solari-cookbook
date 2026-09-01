Draft — post to LinkedIn or X, attach report.png + a screenshot of the opened PR.

---

Built a Solari use case for the Pinetree Research intern challenge.

An agent that turns a GitHub bug report into a pull request:

- a @getsolari cloud browser reads the issue
- a Solari sandbox clones the repo and reproduces the bug with a failing test
- sbx.git pushes the branch, the GitHub API opens the PR
- back to the browser to screenshot the report

One key, three primitives, one linear pipeline. Runs on the free tier in a few
minutes.

Code: <FORK_URL>/tree/main/examples/issue-repro-agent-py
The PR it opened: <PR_URL>

@harrychow_ @getsolari

Built with Claude.
