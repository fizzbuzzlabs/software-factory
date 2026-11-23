// Installs this skill's npm deps (recorder + image helper) into this directory on
// first use and picks a Chromium that launches. Nothing runs `npm ci` in a cloud
// session, and the plugin cache is re-pulled on every version bump, so record.mjs
// and image.mjs can't assume node_modules exists. Imports only node: builtins —
// it runs before any dep does.
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { copyFile, mkdir, readFile, rename, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
// One install for both entry points: a dep missing here (e.g. an install that
// predates image.mjs) makes the whole set re-install once.
const DEPS = ['playwright', 'ffmpeg-static', 'pngjs', 'pixelmatch']
// All transient state is named `.deps-*` (gitignored in the factory checkout).
const LOCK = join(HERE, '.deps-install.lock')
const FAILED = join(HERE, '.deps-install.failed')
const FFMPEG_FAILED = join(HERE, '.deps-ffmpeg.failed')
const INSTALL_TIMEOUT_MS = 10 * 60_000
const LOCK_STALE_MS = INSTALL_TIMEOUT_MS + 5 * 60_000
const WAIT_TIMEOUT_MS = LOCK_STALE_MS + 5 * 60_000
const FFMPEG_TIMEOUT_MS = 3 * 60_000
const FFMPEG_RETRY_MS = 60 * 60_000

export class DepsError extends Error {}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const note = (msg) => console.error(`verifier-web: ${msg}`)

function tail(run, lines = 25) {
  if (run.error) return String(run.error.message ?? run.error)
  const out = `${run.stdout ?? ''}\n${run.stderr ?? ''}`.trim()
  return out.split('\n').slice(-lines).join('\n') || `exit ${run.status ?? run.signal}`
}

// ESM resolution, exactly what record.mjs's `import()` will do. Deliberately not
// require.resolve: that honors NODE_PATH, which can point at a global playwright
// the ESM import can't see.
function depsResolve() {
  try {
    for (const dep of DEPS) import.meta.resolve(dep)
    return true
  } catch {
    return false
  }
}

const ffmpegStaticBin = (modules = join(HERE, 'node_modules')) =>
  join(modules, 'ffmpeg-static', process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg')

// A failed ffmpeg fetch is retried at most hourly, so a network that can't reach
// the binary's host doesn't cost every run a download timeout.
function ffmpegCoolingDown() {
  try {
    return Date.now() - JSON.parse(readFileSync(FFMPEG_FAILED, 'utf8')).at < FFMPEG_RETRY_MS
  } catch {
    return false
  }
}

const depsReady = () => depsResolve() && (existsSync(ffmpegStaticBin()) || ffmpegCoolingDown())

// ffmpeg-static's postinstall streams its download straight onto the final path,
// so a torn download looks installed, and run as an npm script its failure fails
// the whole install. Run it apart, against a temp path (FFMPEG_BIN redirects it),
// and rename into place: a concurrent reader sees no binary or a whole one.
// Best-effort — a missing binary costs the mp4 (system ffmpeg or webm card), never
// the run. Returns null on success, else the reason.
async function fetchFfmpeg(modules) {
  const bin = ffmpegStaticBin(modules)
  const tmp = `${bin}.download-${process.pid}`
  const run = spawnSync(process.execPath, ['install.js'], {
    cwd: join(modules, 'ffmpeg-static'),
    encoding: 'utf8',
    timeout: FFMPEG_TIMEOUT_MS,
    env: { ...process.env, FFMPEG_BIN: tmp },
  })
  try {
    if (run.error || run.status !== 0 || !existsSync(tmp)) return tail(run, 5)
    for (const ext of ['.README', '.LICENSE']) await rename(tmp + ext, bin + ext).catch(() => {})
    await rename(tmp, bin)
    await rm(FFMPEG_FAILED, { force: true })
    return null
  } finally {
    for (const ext of ['', '.README', '.LICENSE']) await rm(tmp + ext, { force: true })
  }
}

async function noteFfmpegFailure(reason) {
  await writeFile(FFMPEG_FAILED, JSON.stringify({ at: Date.now(), reason })).catch(() => {})
  note(`ffmpeg-static binary download failed — the mp4 falls back to a system ffmpeg, retried in an hour:\n${reason}`)
}

function pidAlive(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch (e) {
    return e.code === 'EPERM'
  }
}

// mkdir is atomic: exactly one concurrent caller creates the lock. A lock whose
// owner died, or that outlived any install, is stale — moved aside (rename is
// atomic, so one breaker wins) and retried. Breaking a live lock by mistake only
// costs a duplicate install: each install builds in its own staging dir and
// lands with an atomic rename.
async function tryLock() {
  try {
    await mkdir(LOCK)
    await writeFile(join(LOCK, 'owner'), JSON.stringify({ pid: process.pid, at: Date.now() }))
    return true
  } catch (e) {
    if (e.code !== 'EEXIST') throw e
  }
  let owner = null
  try {
    owner = JSON.parse(await readFile(join(LOCK, 'owner'), 'utf8'))
  } catch {
    // Owner file not written yet (holder is between mkdir and writeFile) or the lock just went away.
  }
  const since = owner?.at ?? (await stat(LOCK).catch(() => null))?.mtimeMs ?? Date.now()
  if ((owner && !pidAlive(owner.pid)) || Date.now() - since > LOCK_STALE_MS) {
    const aside = `${LOCK}.stale-${process.pid}-${Date.now()}`
    await rename(LOCK, aside).then(
      () => rm(aside, { recursive: true, force: true }),
      () => {},
    )
  }
  return false
}

// npm ci into a private staging dir, then rename its node_modules into place, so
// a concurrent reader never sees a half-written node_modules and a failed
// install leaves nothing behind. Install scripts are skipped; the only one that
// matters, ffmpeg-static's binary download, runs as fetchFfmpeg.
async function install() {
  const staging = join(HERE, `.deps-staging-${process.pid}-${Date.now()}`)
  await mkdir(staging)
  try {
    for (const f of ['package.json', 'package-lock.json']) await copyFile(join(HERE, f), join(staging, f))
    const run = spawnSync('npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund', '--loglevel=error'], {
      cwd: staging,
      encoding: 'utf8',
      timeout: INSTALL_TIMEOUT_MS,
    })
    if (run.error || run.status !== 0) {
      throw new DepsError(`couldn't install deps — \`npm ci\` failed in ${HERE}:\n${tail(run)}`)
    }
    const ffmpegFailure = await fetchFfmpeg(join(staging, 'node_modules'))
    if (ffmpegFailure) await noteFfmpegFailure(ffmpegFailure)
    if (depsResolve()) return // a broken lock let another install land first
    const target = join(HERE, 'node_modules')
    if (existsSync(target)) await rename(target, join(staging, 'node_modules.broken'))
    await rename(join(staging, 'node_modules'), target)
  } finally {
    await rm(staging, { recursive: true, force: true })
  }
}

// Make every DEPS entry importable from this directory, installing them on first
// use, and re-fetch a missing ffmpeg binary. Concurrent callers on one directory
// serialize on a lock; those that waited reuse the winner's result instead of
// re-running npm ci.
export async function ensureDeps() {
  if (depsReady()) return
  const waitStart = Date.now()
  let announced = false
  while (!(await tryLock())) {
    if (!announced) note('another run is installing deps here — waiting')
    announced = true
    await sleep(1000)
    if (depsReady()) return
    const failed = await readFile(FAILED, 'utf8').then(JSON.parse, () => null)
    if (failed && failed.at >= waitStart) throw new DepsError(failed.message)
    if (Date.now() - waitStart > WAIT_TIMEOUT_MS) {
      throw new DepsError(`couldn't install deps — timed out waiting on the install lock ${LOCK}`)
    }
  }
  try {
    if (!depsResolve()) {
      note(`installing deps (first use) — npm ci in ${HERE}`)
      const t0 = Date.now()
      try {
        await install()
      } catch (e) {
        const message = e instanceof DepsError ? e.message : `couldn't install deps — ${e.message}`
        await writeFile(FAILED, JSON.stringify({ at: Date.now(), message })).catch(() => {})
        throw new DepsError(message)
      }
      await rm(FAILED, { force: true })
      note(`deps installed in ${((Date.now() - t0) / 1000).toFixed(0)}s`)
    }
    if (depsResolve() && !depsReady()) {
      note('ffmpeg-static binary missing — fetching it')
      const reason = await fetchFfmpeg(join(HERE, 'node_modules'))
      if (reason) await noteFfmpegFailure(reason)
    }
  } finally {
    await rm(LOCK, { recursive: true, force: true })
  }
  if (!depsResolve()) {
    throw new DepsError(`couldn't install deps — npm ci succeeded but ${DEPS.join(' / ')} still don't resolve from ${HERE}`)
  }
}

// The mp4 encoder: FFMPEG_BIN, ffmpeg-static's binary, or a system ffmpeg (cloud
// containers ship /usr/bin/ffmpeg) — the first that runs, so a truncated binary
// falls through. null when none does; record.mjs then lands the webm as a card.
export function resolveFfmpeg() {
  const candidates = [process.env.FFMPEG_BIN, ffmpegStaticBin(), 'ffmpeg', '/usr/bin/ffmpeg']
  for (const bin of candidates.filter(Boolean)) {
    if (spawnSync(bin, ['-version'], { stdio: 'ignore', timeout: 10_000 }).status === 0) return bin
  }
  return null
}

// Preinstalled Chromiums outside Playwright's revision-pinned layout. Cloud
// containers ship one at /opt/pw-browsers with PLAYWRIGHT_BROWSERS_PATH set and
// browser downloads disabled; its revision may differ from the one this
// playwright version expects, so it's launched by path.
function fallbackChromiums() {
  const roots = [...new Set([process.env.PLAYWRIGHT_BROWSERS_PATH, '/opt/pw-browsers'].filter(Boolean))]
  const found = []
  for (const root of roots) {
    found.push(join(root, 'chromium'))
    let dirs = []
    try {
      dirs = readdirSync(root).filter((d) => /^chromium-\d+$/.test(d))
    } catch {
      continue
    }
    dirs.sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
    for (const d of dirs) for (const sub of ['chrome-linux64', 'chrome-linux']) found.push(join(root, d, sub, 'chrome'))
  }
  return [...new Set(found)].filter((p) => existsSync(p))
}

const firstLine = (e) => String(e?.message ?? e).split('\n')[0]

// Launch Playwright's own Chromium when present; else a preinstalled one; else —
// only where browser downloads are allowed — `playwright install chromium`.
export async function launchChromium(chromium, options = {}) {
  const tried = []
  try {
    return await chromium.launch(options)
  } catch (e) {
    tried.push(`playwright's chromium: ${firstLine(e)}`)
  }
  for (const executablePath of fallbackChromiums()) {
    try {
      const browser = await chromium.launch({ ...options, executablePath })
      note(`using preinstalled Chromium ${executablePath} (${browser.version()})`)
      return browser
    } catch (e) {
      tried.push(`${executablePath}: ${firstLine(e)}`)
    }
  }
  if (process.env.PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD) {
    tried.push('`playwright install chromium` skipped: PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD is set')
  } else {
    note('no usable Chromium found — running `playwright install chromium`')
    const run = spawnSync(process.execPath, [join(HERE, 'node_modules', 'playwright', 'cli.js'), 'install', 'chromium'], {
      encoding: 'utf8',
      timeout: INSTALL_TIMEOUT_MS,
    })
    if (run.error || run.status !== 0) {
      tried.push(`\`playwright install chromium\` failed: ${tail(run, 5)}`)
    } else {
      try {
        return await chromium.launch(options)
      } catch (e) {
        tried.push(`playwright's chromium after install: ${firstLine(e)}`)
      }
    }
  }
  throw new DepsError(`no usable Chromium —\n  ${tried.join('\n  ')}`)
}
