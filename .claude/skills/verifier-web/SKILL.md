---
name: verifier-web
description: Evidence-capture protocol for a web app's browser surface — drives an already-running app with Playwright, records a video, an inline-playable mp4, and a trace, returns artifact paths to cite in a verification report, and (given a `--ticket`) lands the mp4 on the Linear ticket as an inline-player comment (scrub + speed) — a mechanical step of the run. Also owns the sanctioned screenshot image helper — crop, resize, pixel-diff compare, or pair two screens (e.g. iOS vs web) side by side — use it instead of PIL, ImageMagick, or sips. Invoked by `verify` via its `verifier-*` lookup. Does NOT start servers, scope the diff, or decide the verdict.
argument-hint: "[--url <base-url>] --flow <abs-path> --out <abs-dir> [--ticket <ABC-123>] [--verdict PASS|FAIL|BLOCKED]"
---

# Verifier — web surface

Wraps a verification session in a recorded Playwright run, so a reviewer can replay what you saw instead of trusting a screenshot you chose. Produces `session.webm`, `session.mp4`, and `trace.zip` from a running app and a flow; `image.mjs` crops, resizes, compares, and pairs screenshots for image evidence.

## Steps

### 1. Get the app running

The app repo's `run-*` skill owns build, launch, and ports. Its headless launcher — the wrapper that boots the app, runs one command against it, and tears it down — takes free ports per run, never fixed ones: parallel dev workers each verify from their own worktree, and a pinned port turns the second into a collision. It hands the wrapped command the client's base URL as the `APP_URL` env var and as the literal `{appUrl}`, substituted in the command's argv (worker briefs forbid `$(…)` and computed values), and points every server-to-server URL at the ports it allocated. A launcher that still pins a port and finds it serving refuses to start; the verdict names that BLOCKED as `port-busy` — a resource collision, not a defect in the change.

Confirm the base URL answers before recording.

### 2. Write the flow

A flow is a module default-exporting an async function that takes Playwright's `page`:

```js
export default async function (page) {
  await page.goto('/')
  // drive the changed code
}
```

It imports nothing. The harness owns every Playwright import, so a flow resolves no `node_modules` and can live in the app repo next to the selectors it uses. App-specific helpers belong there, not here.

### 3. Record

```bash
node ${CLAUDE_SKILL_DIR}/record.mjs \
  --flow /abs/path/to/flow.mjs --out /abs/out/dir \
  --ticket ABC-123 --verdict PASS
```

`--url` defaults to `APP_URL`, so a run under the launcher omits it. Pass it only against an app started some other way.

The first run of `record.mjs` or `image.mjs` installs the skill's deps (and, for `record.mjs`, Chromium if none is available), so it's slower. Don't run `npm ci` or `playwright install` yourself: this directory is the plugin cache, shared by every worktree and session on the machine. Both scripts install under a lock into a staging dir and swap it in whole; a raw `npm ci` deletes `node_modules` out from under every run beside it.

- **Exit 1** — the flow threw. Artifacts are still recorded and the stack printed; read them before re-running.
- **Exit 3** — deps couldn't install or no Chromium launched. Its `verifier-web: …` line names the failed step; report BLOCKED with that line.

Open a trace with `npx playwright show-trace <path>`.

### 4. Land evidence on the ticket (automatic)

Pass `--ticket <ID>` and the run lands its evidence on that Linear issue itself; don't upload it separately.

- **Primary — `session.mp4` → comment embed**: an h.264 mp4 referenced in a comment body, which Linear renders as a true inline `<video>` player — scrub timeline plus a playback-speed control (`1×` button, or `<` / `>`). An attachment card can't do this; only a body embed becomes a player.
- **Fallback — `session.webm` → attachment card**: only when ffmpeg can't build the mp4. The raw recording lands as a downloadable card.

Details:

- Lands for every ticketed run — PASS / FAIL / BLOCKED alike (a failing flow's recording is evidence too). Omit `--ticket` and nothing is uploaded.
- `--verdict` is optional and only decorates the comment/attachment title and filename (`ABC-123 verification — PASS`, `abc123-PASS.mp4`); the upload does not depend on it.
- Auth reuses `LINEAR_API_TOKEN` — the same personal API key the Linear MCP uses (raw token, no `Bearer`). If it's unset, or the ticket doesn't resolve, or Linear errors, the run logs a `linear (…)` note and still succeeds; a landing failure never fails the verification.

`session.mp4` is trimmed to open on first paint, so it shows the app rather than the blank screen before it renders; a run that never paints keeps its blank as evidence. It keeps real speed (the viewer changes it in the player). `ffmpeg` ships via the `ffmpeg-static` dep, including `libx264` for the mp4. Its binary download is best-effort: a run that finds it missing re-fetches it (at most hourly after a failure) and meanwhile uses a system `ffmpeg`; if neither runs, the mp4 is skipped (webm-card fallback) while the webm and trace still succeed. A missing ffmpeg never blocks a run.

## Image helper — crop, resize, compare, pair

PNG in, PNG out:

```bash
node ${CLAUDE_SKILL_DIR}/image.mjs info    <in.png>
node ${CLAUDE_SKILL_DIR}/image.mjs crop    <in.png> <out.png> --x <px> --y <px> --w <px> --h <px>
node ${CLAUDE_SKILL_DIR}/image.mjs resize  <in.png> <out.png> (--width <px> | --height <px> | --scale <factor>)
node ${CLAUDE_SKILL_DIR}/image.mjs compare <a.png> <b.png> [--diff <out.png>] [--threshold 0.1] [--fit] [--fail-above <ratio>]
node ${CLAUDE_SKILL_DIR}/image.mjs pair    <a.png> <b.png> <out.png> [--height <px>] [--gap 16]
```

- Each op prints one JSON line; `compare`'s carries `mismatched` and `ratio`. Cite those numbers rather than eyeballing.
- `compare` refuses differing sizes (exit 2): crop both to the same region and resize to matching dimensions first. `--fit` scales b onto a for a quick ratio, and warns when the aspects differ — a stretched ratio means nothing.
- For a paired iOS/web audit, `pair` the two screens at a common height (default: the shorter) into one image to cite, and `compare` only regions that should render identically.
- `--fail-above <ratio>` exits 1 above that ratio, for a scripted drift check; without it `compare` only reports.
- Exit 2 is bad usage or a non-PNG input; exit 3 is a deps failure, reported as in step 3.

## Rules

- Never use Python `PIL`/Pillow, ImageMagick (`magick`/`convert`), or `sips` on screenshots: none is reliably installed in cloud or local. `image.mjs` is the one sanctioned path. When it lacks an op you need, report the gap; don't improvise.
- Use the `playwright` library, never `@playwright/test`. A verification is not a test: there are no assertions, and the verdict comes from observation rather than `expect()`.
- Never install Playwright into the app repo; the dep lives in this skill's directory.
