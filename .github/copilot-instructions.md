# Pull request review

When reviewing a pull request:

- Prioritize regressions, security issues, and changes that break skill
  installation or discovery.
- For packaging changes, verify that the affected skill's metadata and the
  Copilot and Claude marketplace entries stay consistent with `AGENTS.md`.
- Flag changes to tool permissions, subprocesses, filesystem access, or
  network access. Identify the input and the trust boundary involved.
- For behavior changes, flag missing tests for failure paths and permission
  boundaries where applicable.
- Report actionable findings on changed lines. Explain the impact and
  suggest the smallest effective fix. Skip style-only comments.
