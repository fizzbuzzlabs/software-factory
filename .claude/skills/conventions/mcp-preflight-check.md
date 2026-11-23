# Convention: MCP Preflight Check

A skill that depends on an MCP server (Linear, GitHub, Notion and so on) checks the server is loaded before it does anything else, and halts when it isn't. Never route around a missing MCP: a skill that carries on produces a degraded artifact, or writes somewhere the user didn't ask for, and nobody finds out.

## Declaring

A SKILL.md that touches an MCP lists its servers by short name in a `## Required MCPs` section near the top. Everything listed is required. A skill that could run without one of them is two skills.

## Step 0

MCP tools are **deferred** in this harness: their schemas aren't in the prompt until `ToolSearch` loads them. So before any other work:

1. Resolve one tool from each declared server with `ToolSearch`, by exact name: `select:mcp__linear__list_issues` for `linear`, `select:mcp__github__list_pull_requests` for `github`.
2. If a search returns nothing, stop. Say which MCP is missing and that the skill needs it, and end the turn. Don't gather context "for later", and don't put the output somewhere else.
3. Otherwise go on. The tools stay loaded for the session.

## Agents

An agent whose `tools` frontmatter lists an MCP server (`mcp__github`, `mcp__linear`) holds the grant, but each tool is still deferred: calling one cold answers "No such tool available". Load it by exact name with `ToolSearch` first; one `select:` can name several tools. There is no per-server skill to invoke.

An agent with no grant for a server reports its outcome to whatever spawned it. That operation isn't its job, and it never routes around the missing grant.

Failures while a tool runs (rate limits, auth errors) are each skill's to handle, not this check's.
