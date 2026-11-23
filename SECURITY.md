# Security policy

## Reporting a problem

Report security problems privately. Don't open a public issue or PR for one.

Use GitHub's private vulnerability reporting: on this repository's **Security** tab, choose
**Report a vulnerability**. The report stays private between you and the maintainers unless they
publish it.

Include:

- what the problem is and what someone could do with it
- the steps to reproduce it
- the plugin version (`version` in `plugin/.claude-plugin/plugin.json`)

If a report leads to a fix, we'll credit you in it unless you'd rather we didn't.

## What counts

The factory runs agents that read tickets, run shell commands and open PRs, so a security problem
here is usually one of these:

- a way around a hook guard, such as getting an agent to print a secret or run a destructive git
  command the guard is meant to stop
- a skill, agent or hook that leaks a secret into a transcript, a Linear ticket, a commit or a PR
- ticket text, a web page or another input that can steer an agent into writing outside its
  worktree or acting beyond its task
- a control template that weakens an app repo's CI once installed

Problems in Claude Code, Linear, GitHub or an MCP server itself belong to that vendor. Report them
there.

## Supported versions

Only the latest plugin version gets fixes. App repos pick up a fix when they update the plugin.
