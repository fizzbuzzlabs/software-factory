#!/usr/bin/env node
// Renders the architecture explorer headless with a set of touched nodes marked,
// screenshots the diagram, and (given --ticket) attaches the image to the Linear
// issue via the same GraphQL upload verifier-web uses for its gif. Reuses the
// Playwright vendored in the sibling verifier-web skill — no second install.
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
// The evaluate() body below is browser-only (references document) and must never
// run under node. Its browser runtime lives in the sibling verifier-web install
// (Playwright module + a chromium binary), which an isolated worktree may lack.
// Load Playwright behind a guard; if the module is absent, SKIP cleanly (exit 0)
// so this render step never fails workflow-implement's PR-open over a missing dep.
let chromium
try {
  ({ chromium } = await import(new URL('../verifier-web/node_modules/playwright/index.mjs', import.meta.url)))
} catch {
  console.log('highlight  (skipped: Playwright runtime unavailable — run verifier-web setup to enable the delta image)')
  process.exit(0)
}
const { attachToLinear } = await import('../verifier-web/linear-upload.mjs')

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i].replace(/^--/, ''), process.argv[i + 1])
const htmlPath = args.get('html')
const outArg = args.get('out')
if (!htmlPath || !outArg) {
  console.error('usage: highlight.mjs --html <arch.html> --out <dir> --changed <id,id> [--edited <id,id>] [--edges <from|to|kind,...>] [--removed <from|to|kind,...>] [--ticket <ABC-1>] [--summary <text>]')
  process.exit(2)
}
const parseEdges = (val) => (val || '').split(',').map((s) => s.trim()).filter(Boolean).map((s) => s.split('|'))
const parseIds = (val) => (val || '').split(',').map((s) => s.trim()).filter(Boolean)
const changed = parseIds(args.get('changed'))
// Edited nodes (content-only edits to already-mapped files, from diff.editedNodes
// minus the changed set) are drawn dashed-amber with no glow; structural priority
// means a node in both sets renders as changed, never edited.
const edited = parseIds(args.get('edited'))
// Changed edges (net-new or kind-modified, from diff.edgesChanged) are drawn
// solid; deleted edges (from diff.edgesDeleted) are drawn as red dotted lines.
// Both are from|to|kind triples; absent → draw none of that set.
const edges = parseEdges(args.get('edges'))
const removed = parseEdges(args.get('removed'))
const outDir = resolve(outArg)
await mkdir(outDir, { recursive: true })
const imgPath = resolve(outDir, 'architecture-changes.png')

let browser
try {
  browser = await chromium.launch()
} catch {
  console.log('highlight  (skipped: no chromium binary to render the delta — run verifier-web setup to enable)')
  process.exit(0)
}
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
await page.goto(pathToFileURL(resolve(htmlPath)).href)
await page.waitForSelector('.node')

// Drive the explorer: draw ONLY the changed edges (net-new or kind-modified,
// solid) plus the deleted edges (red dotted), then mark the touched node set.
// The explorer exposes no "highlight a set" hook (a ?changed= param is a
// product-repo nice-to-have), so we reuse its own clearEdges/drawEdge globals
// and mark via the DOM it already built. Drawing the full graph (window.drawAll)
// is what buried the delta in edges.
await page.evaluate(({ ids, editedIds, edges, removed }) => {
  const style = document.createElement('style')
  style.textContent =
    '.node.changed{outline:3px solid #f5a623;outline-offset:2px;box-shadow:0 0 0 3px rgba(245,166,35,.35)}' +
    '.node.edited{outline:2px dashed #f5a623;outline-offset:2px}' +
    '.node.faded{opacity:.35}'
  document.head.appendChild(style)
  if (typeof window.clearEdges === 'function') window.clearEdges()
  if (typeof window.drawEdge === 'function') {
    for (const [f, t, k] of edges) window.drawEdge(f, t, k)
    // Deleted edges: draw with the explorer's own geometry (endpoints still
    // exist as nodes), then restyle the just-appended line as a red dotted line.
    const svg = document.getElementById('edges')
    for (const [f, t, k] of removed) {
      try { window.drawEdge(f, t, k) } catch { continue }
      const lines = svg ? svg.getElementsByTagName('line') : []
      const ln = lines[lines.length - 1]
      if (ln) {
        ln.setAttribute('stroke', '#e5484d')
        ln.setAttribute('stroke-dasharray', '5,4')
        ln.setAttribute('opacity', '.9')
      }
    }
  }
  const set = new Set(ids)
  const editedSet = new Set(editedIds)
  for (const el of document.querySelectorAll('.node')) {
    if (set.has(el.dataset.id)) el.classList.add('changed')
    else if (editedSet.has(el.dataset.id)) el.classList.add('edited')
    else el.classList.add('faded')
  }
}, { ids: changed, editedIds: edited, edges, removed })

const diagram = (await page.$('#diagram')) || page
await diagram.screenshot({ path: imgPath })
await browser.close()
console.log(`image   ${imgPath}`)

const ticket = args.get('ticket')
if (ticket) {
  const token = process.env.LINEAR_API_TOKEN
  if (!token) {
    console.log(`linear  (skipped: LINEAR_API_TOKEN not set — cannot attach to ${ticket})`)
  } else {
    const summary = args.get('summary') || `${changed.length} node(s) changed, ${edited.length} edited`
    const result = await attachToLinear({
      token,
      ticket,
      filePath: imgPath,
      filename: `${ticket.toLowerCase()}-architecture.png`,
      contentType: 'image/png',
      title: `${ticket} architecture delta`,
      subtitle: summary,
    })
    console.log(result.ok ? `linear  attached to ${ticket}: ${result.url}` : `linear  (attach failed: ${result.note})`)
  }
}
