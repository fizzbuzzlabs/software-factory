---
name: meta-add-mcp-server
description: Add a new MCP server to the software factory repo end-to-end — research the package, wire .mcp.json, document the credential in docs/mcp-credentials.md, and allow the server — while spelling out the steps the user must do by hand: the secret, and the cloud Setup-script entries. Use for "add the X MCP server", "wire up X via MCP", "/meta-add-mcp-server". Does NOT handle secret values itself.
argument-hint: "[service]"
---

# Meta — Add MCP Server

Stand up a new MCP server the way the existing servers in `.mcp.json` are set up. Do the repo edits directly; hand the user the one step that touches a real secret. Split every report into **What I'll do** (automated) and **What you need to do** (manual).

## Conventions this skill follows

- `.claude/skills/conventions/execution-mode.md` — detect mode; in headless mode never block on a manual secret step, just record it.

## Steps

### 1. Research the server

Find the best MCP package for the service. Match a pattern already in `.mcp.json`: either a **stdio** server (`npx -y <pkg>` / `uvx --from git+<repo> <entrypoint>`) authenticated by one env var, or a **hosted HTTP** server (`type: http`, a `url`, optional auth `headers`). Verify the exact entrypoint from source (`package.json` `bin`, `pyproject [project.scripts]`) — don't guess. Prefer the official server when one exists; flag the trade-off when the only options are a hosted OAuth-only server vs. a community API-key one. Record: connection type, run command or URL, the env-var name for the secret, and the URL where the user generates the key.

### 2. Wire `.mcp.json`

Add an entry under `mcpServers` mirroring the existing ones. Reference the secret only as `${SERVICE_ENV_VAR}` — never the literal value — in the `env` block (stdio) or an `Authorization` / auth header (http). Validate the JSON. (`.mcp.json` is not protected — edit directly.)

### 3. Hand off the secret

This is **the user's** to do — never take the secret value yourself. Tell them to:
1. Generate the key at the URL from step 1.
2. Make `SERVICE_ENV_VAR` available via the **launchd plist pattern** in `docs/mcp-credentials.md` — a token file under `~/.<service>-mcp/` plus a `~/Library/LaunchAgents/com.<you>.<service>-token.plist` that `launchctl setenv`s it at login. launchd puts the var in the user-session environment, so it reaches both the desktop app and every git worktree; this repo has no `.env`.
3. Restart Claude Code (or `launchctl kickstart -k "gui/$(id -u)/com.<you>.<service>-token"`) so the server reconnects and picks up the new env var.

### 4. Document

In `docs/mcp-credentials.md`, add the token under **Tokens** (what it is, where to get it) and the server to the cloud setup (its host and its `claude mcp add` line).

### 5. Allow the tools

Add the server-level rule `mcp__<server>` to `permissions.allow` in `.claude/settings.json` via the `update-config` skill (create the file if absent). Use the server-level form, not per-tool `mcp__<server>__*`. Project `.mcp.json` servers connect on their own, but their tools still prompt for approval until this entry exists.

### 6. Stage on a branch

Commit the `.mcp.json`, settings, and `docs/mcp-credentials.md` changes on a feature branch (never main). Leave the PR for the user to open, and only commit when they ask.

## Cloud sessions

A cloud session can't rely on the repo's `.mcp.json`. For an HTTP server that must run in the cloud, tell the user to add its host under the environment's Network access, its key as a network secret for that host, and `claude mcp add --transport http --scope user <server> <url>`, with no auth header, to the Setup script (`docs/mcp-credentials.md`, "In a cloud environment"). A stdio server or a multi-file credential (OAuth refresh tokens, service-account JSON) doesn't fit a network secret: flag it rather than guessing.

## Rules

- Never handle, request, or write the secret value — only reference it as `${ENV_VAR}` and let the user place it via the launchd plist and the environment's network secrets.
- Match an existing `.mcp.json` pattern; prefer the official server, and flag OAuth-vs-API-key trade-offs rather than deciding silently.
