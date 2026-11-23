# MCP credentials

The factory needs two MCP servers, Linear and GitHub. This covers getting their tokens to
Claude Code on a Mac and in a cloud environment. Paper, the optional third server, runs on
your Mac with no token and isn't needed in the cloud.

## Tokens

- **Linear:** a personal API key (`lin_api_…`) from **Settings → Security & access → API →
  Personal API keys**. It acts as you. Use a separate key for each machine and cloud environment,
  so you can revoke one without breaking the others.
- **GitHub** (on a Mac only; the cloud supplies GitHub): a fine-grained token with Contents, Pull
  requests and Checks (read) on your repos, or a classic token with `repo`. Name its variable
  `GITHUB_PERSONAL_ACCESS_TOKEN`, not `GITHUB_TOKEN` or `GH_TOKEN`: `gh` reads those, so setting
  either would override `gh auth login`.

## On a Mac

The repo's `.mcp.json` ([setup](setup.md) step 2) reads `${LINEAR_API_TOKEN}` and
`${GITHUB_PERSONAL_ACCESS_TOKEN}` from the environment. A repo `.env` doesn't work: the desktop app doesn't read your shell, and a worker's
worktree has no `.env`. Instead, keep each token in a file (`chmod 600`) and export it at login
with a launchd plist, which every launch path and worktree inherits. One plist per token, per
machine, serves every repo:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.<you>.<service>-token</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>-c</string>
    <string>launchctl setenv <VAR> "$(cat $HOME/.<service>-mcp/<token-file>)"</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```

Save it as `~/Library/LaunchAgents/com.<you>.<service>-token.plist`, then:

- First time: `launchctl load ~/Library/LaunchAgents/com.<you>.<service>-token.plist`
- After changing the token file: `launchctl kickstart -k "gui/$(id -u)/com.<you>.<service>-token"`

Restart Claude Code, then check: `launchctl getenv LINEAR_API_TOKEN` prints the key, and
`claude mcp list` shows `linear` and `github` connected.

## In a cloud environment

Set up the environment like this:

| Field | Set to |
|---|---|
| Repositories | The app repo, plus every repo in its `Sibling repos:` line |
| Network access | Limited, plus `mcp.linear.app` |
| Network secrets | Your Linear key, for `mcp.linear.app` |
| Setup script | Below |

```bash
#!/bin/bash
claude plugin marketplace add fizzbuzzlabs/software-factory
claude plugin install software-factory@software-factory --scope project
claude mcp add --transport http --scope user linear https://mcp.linear.app/mcp
```

- **Linear** is defined at user scope, with no header: the network secret adds the key to each
  request, so it never enters the session.
- **GitHub** needs nothing. The cloud supplies its own `github` server, with the `mcp__github__*`
  tools the skills call.
- **The setup script** installs the plugin because a cloud session doesn't add a repo's
  marketplaces itself. It has no GitHub credential, so it can't clone a private repo. If your
  factory is private, add it to Repositories too, and point the first line at the clone:
  `claude plugin marketplace add /home/user/software-factory`.

With more than one repository, the session doesn't read any repo's `.mcp.json`. With a single
repository it does, but its `linear` entry is set aside because `LINEAR_API_TOKEN` is unset, so
the user-scope server answers. Either way, `claude mcp list` may show the repo's entries as
pending, with a warning about unset variables; that's expected. Don't set `LINEAR_API_TOKEN` in a
cloud environment: the repo's entry could then take over and send that token instead of the
network secret. Both setups were tested.

## Paper (optional)

Paper is only for `/workflow-freeze-design`, which turns a Paper design into files committed to
the repo. Its server runs inside Paper Desktop on your Mac, with no token. It needs no cloud
setup: pipeline stages in the cloud read the committed design files instead.

Add it once for your user, so every repo can use it, rather than in a repo's `.mcp.json`, where it
would show as failing for anyone without Paper:

```bash
claude mcp add --transport http --scope user paper http://127.0.0.1:29979/mcp
```

Keep the name `paper`: the skill calls `mcp__paper__*` tools. Paper's own docs suggest its **Add
to Claude** button or the `paper-desktop@paper` plugin instead. A plugin's server gets a longer
name, so the skill won't find it.

The server only answers while Paper Desktop is open with a file open; otherwise the connection is
refused. To check, open a file in Paper Desktop: `claude mcp list` should show `paper` connected.

## Adding an MCP server

Run `meta-add-mcp-server`. Give the new server's token its own plist, add it to the cloud setup
(a network secret for its host, and a `claude mcp add --scope user` line), and add it to
**Tokens** above.
