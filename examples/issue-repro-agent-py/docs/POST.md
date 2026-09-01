Draft — post to LinkedIn or X, attach docs/report.png + docs/pr.png.

---

Built a Solari use case for the Pinetree Research intern challenge.

An agent that turns a GitHub bug report into a pull request:

- a @getsolari cloud browser reads the issue
- a Solari sandbox clones the repo and reproduces the bug with a failing test
- the sandbox applies a fix, re-runs the test green
- sbx.git pushes the branch, the GitHub API opens the PR
- back to the browser to screenshot the report

One key, three primitives, one linear pipeline. Runs on the free tier in a few
minutes.

Code: https://github.com/SavvyShivam/solari-cookbook/tree/feat/issue-repro-agent/examples/issue-repro-agent-py
The PR it opened: https://github.com/SavvyShivam/repro-agent-demo/pull/5

@harrychow_ @getsolari

Built with Claude + Groq (openai/gpt-oss-120b for the fix step).
