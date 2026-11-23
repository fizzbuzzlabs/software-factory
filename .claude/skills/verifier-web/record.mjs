#!/usr/bin/env node
// Records a Playwright session against a running app. The flow supplies the
// driving; this file owns every Playwright import so flows stay resolution-free.
// Playwright is loaded by dynamic import() after ensureDeps() installs it on
// first use — a static import would fail before it could run.
import { spawnSync } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { DepsError, ensureDeps, launchChromium, resolveFfmpeg } from './ensure-deps.mjs'
import { attachToLinear, commentVideoToLinear } from './linear-upload.mjs'

// A missing dep or browser exits 3 with a `verifier-web: …` line naming the
// failed step — the caller's BLOCKED, distinct from a flow that threw (exit 1).
function exitOnDepsError(e) {
  if (!(e instanceof DepsError)) throw e
  console.error(`verifier-web: ${e.message}`)
  process.exit(3)
}

// Playwright starts recording at page creation, so a slow first paint (e.g. a
// render-blocking asset the headless sandbox can't fetch) leaves a static blank
// screen — dead frames before the app appears. Find that leading freeze so the
// mp4 can open on the app, not a blank. Only a freeze anchored at t=0 counts: an
// interior pause (a turn streaming) is real content and stays. A run that never
// paints has no freeze_end, so its blank is kept as evidence rather than trimmed
// to nothing. Best-effort — any probe failure yields 0 (no trim).
function leadInSeconds(webmPath) {
  const probe = spawnSync(
    ffmpegBin,
    ['-hide_banner', '-i', webmPath, '-vf', 'freezedetect=n=-60dB:d=1', '-map', '0:v', '-f', 'null', '-'],
    { encoding: 'utf8' },
  )
  if (probe.error || probe.status !== 0) return 0
  const log = probe.stderr ?? ''
  const start = log.match(/freeze_start:\s*([\d.]+)/)
  const end = log.match(/freeze_end:\s*([\d.]+)/)
  if (!start || !end || Number(start[1]) > 1) return 0
  return Number(end[1]) // freeze_end is the first painted frame; input seek is frame-accurate
}

// The webm recording, re-encoded to h.264 mp4 — the container Linear's inline
// video player renders reliably (webm is spotty), so a comment embed becomes a
// true player with scrub + speed. `-ss` before `-i` trims the blank lead so it
// opens on the app; even dimensions kept for yuv420p.
function makeMp4(webmPath, mp4Path) {
  if (!ffmpegBin) return { ok: false, note: 'no runnable ffmpeg (ffmpeg-static binary missing, none on the system) — mp4 skipped' }
  const lead = leadInSeconds(webmPath)
  const seek = lead > 0 ? ['-ss', String(lead)] : []
  const run = spawnSync(
    ffmpegBin,
    [
      '-y', '-loglevel', 'error', ...seek, '-i', webmPath,
      '-movflags', '+faststart', '-pix_fmt', 'yuv420p',
      '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', mp4Path,
    ],
    { encoding: 'utf8' },
  )
  if (run.error?.code === 'ENOENT') return { ok: false, note: 'ffmpeg not resolved — mp4 skipped' }
  if (run.status !== 0) return { ok: false, note: `ffmpeg failed — mp4 skipped: ${run.stderr?.trim() ?? ''}` }
  return { ok: true, trimmed: lead }
}

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) {
  args.set(process.argv[i].replace(/^--/, ''), process.argv[i + 1])
}

// --url falls back to APP_URL, which the app's headless launcher exports with
// the ports it allocated for this run.
const url = args.get('url') ?? process.env.APP_URL
const flowArg = args.get('flow')
const outArg = args.get('out')
if (!url || !flowArg || !outArg) {
  console.error(
    'usage: record.mjs [--url <base-url>, default $APP_URL] --flow <abs-path> --out <abs-dir> [--ticket <ABC-123>] [--verdict PASS|FAIL|BLOCKED]',
  )
  process.exit(2)
}

const outDir = resolve(outArg)
await mkdir(outDir, { recursive: true })

const { default: flow } = await import(pathToFileURL(resolve(flowArg)).href)
if (typeof flow !== 'function') {
  console.error(`flow ${flowArg} must default-export an async function (page) => {}`)
  process.exit(2)
}

await ensureDeps().catch(exitOnDepsError)
const { chromium } = await import('playwright')

// The recording lands on the ticket as an mp4 embedded in a comment — a true
// inline player (scrub + speed). ffmpeg ships via the ffmpeg-static dep (incl.
// libx264); a system ffmpeg is the fallback if its binary is missing (see
// SKILL.md).
const ffmpegBin = resolveFfmpeg()

const viewport = { width: 1280, height: 800 }
const browser = await launchChromium(chromium).catch(exitOnDepsError)
const context = await browser.newContext({
  baseURL: url,
  viewport,
  recordVideo: { dir: outDir, size: viewport },
})
await context.tracing.start({ screenshots: true, snapshots: true, sources: true })

const page = await context.newPage()
const video = page.video()
const consoleErrors = []
page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()))
page.on('pageerror', (e) => consoleErrors.push(String(e)))

let failure = null
try {
  await flow(page)
} catch (e) {
  failure = e
} finally {
  await context.tracing.stop({ path: resolve(outDir, 'trace.zip') })
  await context.close()
  if (video) {
    await video.saveAs(resolve(outDir, 'session.webm'))
    await video.delete()
  }
  await browser.close()
}

const webmPath = resolve(outDir, 'session.webm')
console.log(`video   ${webmPath}`)
console.log(`trace   ${resolve(outDir, 'trace.zip')}`)
// The evidence: an h.264 mp4 embedded in a comment (below) renders as a true
// inline player — scrub + speed. If ffmpeg can't build it, fall back to
// attaching the raw webm as a card so a ticketed run still lands something.
let mp4Path = null
let fallback = null
if (video) {
  const candidate = resolve(outDir, 'session.mp4')
  const mp4 = makeMp4(webmPath, candidate)
  const trimNote = mp4.trimmed > 0 ? ` (trimmed ${mp4.trimmed.toFixed(1)}s blank lead-in)` : ''
  console.log(mp4.ok ? `mp4     ${candidate}${trimNote}` : `mp4     (${mp4.note})`)
  if (mp4.ok) mp4Path = candidate
  else fallback = { path: webmPath, contentType: 'video/webm', ext: 'webm', kind: 'Playwright recording (webm)' }
}

// Attach to the ticket as a mechanical step of the run — keyed off --ticket, not
// a follow-up the agent has to remember. Any failure is logged and swallowed so
// a Linear hiccup never fails the verification itself.
const ticket = args.get('ticket')
if (ticket) {
  const token = process.env.LINEAR_API_TOKEN
  if (!token) {
    console.log(`linear  (skipped: LINEAR_API_TOKEN not set — cannot land evidence on ${ticket})`)
  } else {
    const verdict = args.get('verdict')
    const stem = `${ticket.toLowerCase()}${verdict ? `-${verdict}` : ''}`
    const errNote = `${consoleErrors.length} console error(s)${failure ? ' · flow threw' : ''}`

    if (mp4Path) {
      // The inline player: an mp4 embedded in a comment, for scrubbing at speed.
      const result = await commentVideoToLinear({
        token,
        ticket,
        filePath: mp4Path,
        filename: `${stem}.mp4`,
        contentType: 'video/mp4',
        caption: `📹 **${ticket} verification${verdict ? ` — ${verdict}` : ''}** · full recording — scrub and change speed with the player's \`1×\` control (or \`<\` / \`>\`) · ${errNote}`,
      })
      console.log(result.ok ? `linear  video comment on ${ticket}: ${result.url}` : `linear  (video comment failed: ${result.note})`)
    } else if (fallback) {
      // ffmpeg unavailable: attach the raw webm as a card so evidence still lands.
      const result = await attachToLinear({
        token,
        ticket,
        filePath: fallback.path,
        filename: `${stem}.${fallback.ext}`,
        contentType: fallback.contentType,
        title: `${ticket} verification${verdict ? ` — ${verdict}` : ' recording'}`,
        subtitle: `${fallback.kind} · ${errNote}`,
      })
      console.log(result.ok ? `linear  attached to ${ticket}: ${result.url}` : `linear  (attach failed: ${result.note})`)
    } else {
      console.log(`linear  (skipped: no recording artifact to land on ${ticket})`)
    }
  }
}

if (consoleErrors.length) {
  console.log(`console errors (${consoleErrors.length}):`)
  for (const e of consoleErrors) console.log(`  ${e}`)
}
if (failure) {
  console.error(`\nflow threw: ${failure.stack ?? failure}`)
  process.exit(1)
}
