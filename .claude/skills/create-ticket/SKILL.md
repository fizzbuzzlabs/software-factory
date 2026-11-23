---
name: create-ticket
description: "Create a new Linear ticket for the factory — resolve the team from the repo, classify its project, and file it via save_issue with sensible defaults, returning the identifier + URL. The mandatory path for creating a ticket ('create a ticket', 'file a bug', 'open an issue'): the canonical step the ticket-creating skills delegate to and the entry point for an ad-hoc create — never call save_issue to create a ticket directly, always route here. Does NOT investigate a running-app bug (report-bug), explore requirements or write a spec (workflow-questions/workflow-quick), or move status / commit — pure create."
argument-hint: "[title | what the ticket is about] [--team T] [--project P] [--state S] [--label L] [--assignee A] [--related-to ID...]"
---

# Create a Linear Ticket

File one new Linear ticket and return its identifier and URL.

## Required MCPs

- linear

Run the preflight as **Step 0**, per `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`.

## Conventions this skill follows

- `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`
- `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`
- `${CLAUDE_SKILL_DIR}/../conventions/classify-ticket-project.md`

## Execution Mode

Detect mode and apply the universal headless rules per `${CLAUDE_SKILL_DIR}/../conventions/execution-mode.md`.

## Inputs

- **title**, **description** — required. Ad-hoc input too vague to title → ask once, then proceed.
- **team**, **project**, **state**, **labels**, **priority**, **assignee**, **relatedTo** — optional.

## Steps

### 1. Resolve the team

Skip if the caller passed `--team`. Otherwise resolve the Linear team for the current repository via `list_teams`: a `Linear team:` line in the repo's `CLAUDE.md`/`AGENTS.md` wins; else pick the team whose name matches the repo (e.g. `acme-app` → `Acme`). Still ambiguous → ask which team (interactive) or halt naming the candidates (headless).

### 2. Classify the project

Classify the ticket into one of the team's projects per `${CLAUDE_SKILL_DIR}/../conventions/classify-ticket-project.md`, passing any `--project` override as the caller's value.

### 3. File it

One `mcp__linear__save_issue` create with the resolved `team` and `project` and every field the caller passed, never a follow-up update. Always pass a `state`, `Backlog` by default: Linear files an MCP-created issue with none into Triage, which is reserved for reports from app users. Create `bug` or other missing labels via `create_issue_label { name, team }` first.

## Rules

- Pure create — never move a ticket's status, write an artifact, or commit.
- Never file into a personal team.
