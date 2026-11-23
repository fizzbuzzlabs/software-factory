---
name: report-bug
description: "Investigate a bug in the running app and file it to Linear with a root cause. Narrate what's broken; the skill reads the live app's console/network buffer, reproduces the failure by driving the page, cross-references the source, and files a triage-ready ticket in Todo for the dev agent. Use while reviewing the app — 'the X button isn't working', 'this isn't behaving right', 'file a bug on this'."
argument-hint: "[narrate what's broken] [ABC-123 to append to an existing ticket]"
---

# Investigate and File a Bug

The app is open in the Browser pane: you can read its console, its network log, and its DOM, and you can drive it yourself. So don't file a report that says "watch this." Reproduce the failure, find why, and file a ticket the dev agent can start on cold.

## Required MCPs

- linear

Run the preflight as **Step 0**, per `${CLAUDE_SKILL_DIR}/../conventions/mcp-preflight-check.md`. This skill also needs the **Browser pane** and the app running locally; it is interactive-only and cannot run headless.

## What This Skill Does NOT Do

- Fix the bug. Diagnose and file only — the dev agent fixes it.
- Move the ticket further into the pipeline. It lands in **Todo**; the user triages and routes it.

## 1. Harvest the buffer before you touch anything

**Do this first, before any click, navigation, or reload.** The pane's console and network logs are retroactive — they already hold what happened before the user complained, and a reload destroys that record permanently.

- `preview_start { url: "http://localhost:<port>" }` — reuse the open tab; read the port from the product repo's `.claude/launch.json`. **Never reload to "get a clean look."**
- `read_console_messages` and `read_network_requests` — everything, before investigating. `pattern` is a **literal substring**, not a regex: `[deck]` filters; `click|deck` matches nothing and reads as "no logs".
- One inline `computer` screenshot so you can see the failed state.

Then get the narration from the argument (ask "What's broken?" once if empty). The pane does **not** record the user's clicks — ask what they did to get here.

## 2. Reproduce it

Drive the app the way the user does, and distrust your instruments while you do it.

- `console.debug('[marker] <label>')` before each attempt. Buffers are append-only and unclearable; without a marker you *will* read a previous attempt's line as this one's result.
- `read_page` to locate the element by name, then drive it with `computer`.
- Re-read console and network, diff against the baseline: what threw, what fired, what returned non-2xx, what silently did nothing.
- `javascript_tool` to inspect state the DOM doesn't show.

**A measured coordinate is stale the moment you take it** — anything re-rendering from a stream reshuffles its layout between the read and the click. Never conclude a click landed because the maths said so; read back the element it actually hit (the click's logged `target`, or `elementFromPoint`).

**Never substitute a synthetic click for a real one.** `el.click()` from `javascript_tool` skips the pointer sequence, sailing past capture, overlays, hit-testing and disabled states — manufacturing a success path no user can reach. Use it to test a hypothesis about the handler, never to reproduce a user's action.

**Suspect your instrument before the app.** When a control fails only for you, or the user can't reproduce what you saw, prove the method on a control you expect to work — a known-good button, an element outside the suspect container. If the failure reproduces there too, it's your tooling. Check before filing, and don't argue for your finding.

**Couldn't reproduce it?** Say so plainly and file it anyway with the harvested buffer. Never dress a non-reproduction up as a diagnosis.

## 3. Find the cause in the source

**First, rule out "nothing is running."** `ERR_CONNECTION_REFUSED`, or every call to one origin failing at once, means nothing is bound to that port. Confirm with `curl`, check the port against `.claude/launch.json`, and offer to start it — a ten-second diagnosis that otherwise becomes an hour of reading client code for a bug that doesn't exist.

A stack frame or failing request names a file. Read it, follow the handler, and mark the cause honestly:

- **Confirmed** — the evidence proves it (a thrown frame, a 500 on the exact call).
- **Hypothesis** — the code plausibly explains the symptom; say what would confirm it.

Never present a guess as a finding: a confident wrong cause costs the dev agent more than no cause.

Client-side only: you see the calls the browser makes, not stack traces inside the server. For a server-side failure use `preview_logs` when the server is preview-managed, otherwise ask the user for its output.

## 4. Write it up

```markdown
## Summary
[One sentence: what's broken.]

## Steps to reproduce
1. [...]

## Expected / Actual
[...]

## Root cause
[Confirmed | Hypothesis] — [what's wrong, anchored to file:line]

## Evidence
- **Console:** [error + top stack frame, or "none"]
- **Network:** [METHOD URL → status, or "expected POST never fired"]
- **Route/URL:** [...]
- **Build:** [branch + short SHA]
```

## 5. File it

- Create the ticket by invoking the `create-ticket` skill (Skill tool) — never call `save_issue` to create it yourself: `title` = the summary, `description` = the writeup, `state` = `Todo`, `labels` including `bug`, `priority` from any severity signal in the narration.
- Appending to a passed-in `ABC-###` instead → `save_comment` on that issue.

**Attaching a file** (only when the user offers one — visual/design bugs where pixels are the point; pane screenshots cannot be written to disk):
1. `prepare_attachment_upload` — `issue`, `filename`, `contentType`, `size` = `stat -f%z <file>`.
2. `curl -X PUT --data-binary @"<file>"` to `uploadRequest.url`, sending every header from `uploadRequest.headers` verbatim, casing included, or it 403s.
3. `create_attachment_from_upload` — `issue` + `assetUrl`. One file per cycle; signed URLs expire in 60s.

## 6. Report back

Give the ticket identifier + URL and the one-line root cause. It's in **Todo** — offer to route it: `/workflow-quick ABC-###` for a small well-understood fix, `/workflow-questions ABC-###` when the fix needs real design.
