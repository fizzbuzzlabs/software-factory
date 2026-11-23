#!/usr/bin/env node
// Deterministically re-derives the architecture explorer's FILES map and edge
// list (E) from a repo's working tree, and computes the per-PR diff against the
// diagram's current data. Prints a JSON report; with --write, surgically
// rewrites ONLY the FILES and E literal blocks in docs/architecture.html.
//
// Node grouping, prose (sum/eli5), and novel-edge kind classification are NOT
// this script's job — those are the agent's. This script owns everything
// mechanical: file enumeration, the import graph, and the diff.
import { readFile, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

const args = new Map()
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i]
  if (a.startsWith('--')) {
    const key = a.slice(2)
    const next = process.argv[i + 1]
    if (next && !next.startsWith('--')) { args.set(key, next); i++ } else args.set(key, true)
  }
}
const repo = resolve(args.get('repo') || process.cwd())
const htmlPath = resolve(args.get('html') || `${repo}/docs/architecture.html`)
const doWrite = !!args.get('write')
const base = (typeof args.get('base') === 'string' && args.get('base')) || 'origin/main'

// ---- extract a `const NAME = <literal>;` block and eval it as data ----------
function extractBlock(src, name) {
  const m = src.match(new RegExp(`const\\s+${name}\\s*=\\s*`))
  if (!m) return null
  const start = m.index + m[0].length
  const open = src[start]
  const close = open === '{' ? '}' : open === '[' ? ']' : null
  if (!close) return null
  let depth = 0, i = start, inStr = null
  for (; i < src.length; i++) {
    const c = src[i]
    if (inStr) { if (c === '\\') i++; else if (c === inStr) inStr = null; continue }
    if (c === "'" || c === '"' || c === '`') { inStr = c; continue }
    if (c === open) depth++
    else if (c === close) { depth--; if (depth === 0) { i++; break } }
  }
  const literal = src.slice(start, i)
  // eslint-disable-next-line no-new-func
  const value = new Function(`return (${literal})`)()
  return { value, from: m.index, to: i, literalFrom: start, literalTo: i }
}

// ---- file -> node ownership via each node's glob field ----------------------
// Normalize a node's `glob` display string into machine patterns: comma-split,
// with a bare piece (no slash) inheriting the previous piece's directory.
function parseGlob(glob) {
  const pieces = glob.split(',').map((s) => s.trim()).filter(Boolean)
  const out = []
  let dir = ''
  for (const p of pieces) {
    let full = p
    if (!p.includes('/') && dir) full = `${dir}/${p}`
    out.push(full)
    const slash = full.lastIndexOf('/')
    dir = slash >= 0 ? full.slice(0, slash) : dir
  }
  return out
}
function toRegex(pattern) {
  const rx = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*/g, '\0')
    .replace(/\*/g, '[^/]*')
    .replace(/\0/g, '.*')
  return new RegExp(`^${rx}$`)
}
// Specificity: exact (no wildcard) beats any glob; among globs, more literal
// characters wins. Lets Composer's exact path win over views/**.
function specificity(pattern) {
  const hasWild = pattern.includes('*')
  const literal = pattern.replace(/\*/g, '').length
  return (hasWild ? 0 : 100000) + literal
}
// Tests, type declarations, and test scaffolding are never product source.
function isTest(f) {
  return /\.(test|spec)\.[cm]?[jt]sx?$/.test(f)
    || /\.d\.ts$/.test(f)
    || /(^|\/)(__tests__|__mocks__|test-support)\//.test(f)
    || /(^|[/-])test-helpers?\.[cm]?[jt]sx?$/.test(f)
}

async function main() {
  const html = await readFile(htmlPath, 'utf8')
  const N = extractBlock(html, 'N')
  const FILES = extractBlock(html, 'FILES')
  const E = extractBlock(html, 'E')
  if (!N || !FILES || !E) throw new Error('could not locate N / FILES / E literals in ' + htmlPath)

  // Optional per-repo config literal in the target HTML; each field falls back to a
  // generic default when the literal (or that field) is absent, so one script serves
  // every repo and each app self-declares its layout + edge-kind conventions.
  const cfg = extractBlock(html, 'SHOW_CHANGES')?.value || {}
  const roots = Array.isArray(cfg.roots) ? cfg.roots : []           // [] → scan the whole tree
  const ignore = Array.isArray(cfg.ignore) ? cfg.ignore : []        // path prefixes to drop entirely
  const isIgnored = (f) => ignore.some((p) => f === p || f.startsWith(p.replace(/\/+$/, '') + '/'))
  const aggregateFrom = new Set(Array.isArray(cfg.aggregateFrom) ? cfg.aggregateFrom : [])
  const readTargetRe = new RegExp(cfg.readTarget || '-(store|repo)\\.ts$')

  // Build matchers from node globs.
  const matchers = []
  for (const [id, node] of Object.entries(N.value)) {
    for (const pat of parseGlob(node.glob)) {
      matchers.push({ id, pat, re: toRegex(pat), score: specificity(pat) })
    }
  }
  matchers.sort((a, b) => b.score - a.score)

  // Enumerate tracked source files. config.roots narrows the scan; [] = whole tree.
  const tracked = execFileSync('git', ['-C', repo, 'ls-files', ...roots], { encoding: 'utf8' })
    .split('\n')
    .filter(Boolean)
    .filter((f) => /\.(ts|tsx|mjs|js|css|html)$/.test(f))
    .filter((f) => !isTest(f))
    .filter((f) => !isIgnored(f))
    .sort()

  // Assign each file to the highest-specificity matching node.
  const fileNode = new Map()
  const unmapped = []
  for (const f of tracked) {
    const hit = matchers.find((m) => m.re.test(f))
    if (hit) fileNode.set(f, hit.id)
    else unmapped.push(f)
  }

  // New FILES: only nodes that own >=1 tracked source file get re-enumerated;
  // conceptual/runtime nodes (e.g. sqlite, whose files aren't tracked source)
  // keep their current entry verbatim.
  const newFiles = {}
  for (const id of Object.keys(N.value)) {
    const owned = tracked.filter((f) => fileNode.get(f) === id).sort()
    if (owned.length) newFiles[id] = owned
    else if (FILES.value[id]) newFiles[id] = [...FILES.value[id]]
  }

  // ---- import graph -> node edges (flow / read / aggregate) ----------------
  const trackedSet = new Set(tracked)

  // Workspace-package map (monorepo support): package name -> its directory, from
  // every tracked package.json. Lets a bare `@scope/pkg` import resolve to that
  // package's source entry, the way a relative import resolves within one package.
  const pkgMap = new Map()
  for (const pj of execFileSync('git', ['-C', repo, 'ls-files', '*package.json'], { encoding: 'utf8' }).split('\n').filter(Boolean)) {
    if (pj.includes('node_modules/')) continue
    try {
      const name = JSON.parse(await readFile(`${repo}/${pj}`, 'utf8')).name
      if (name) pkgMap.set(name, pj.includes('/') ? pj.slice(0, pj.lastIndexOf('/')) : '.')
    } catch {}
  }

  function resolveImport(fromFile, spec) {
    if (spec.startsWith('.')) {
      const dir = fromFile.slice(0, fromFile.lastIndexOf('/'))
      let base = resolve('/' + dir, spec).slice(1) // normalize ../ and ./
      base = base.replace(/\.(js|ts|jsx|tsx|mjs)$/, '')
      for (const cand of [`${base}.ts`, `${base}.tsx`, `${base}.mjs`, `${base}.js`, `${base}/index.ts`]) {
        if (trackedSet.has(cand)) return cand
      }
      return null
    }
    // Bare workspace-package import: `@scope/pkg` or `@scope/pkg/subpath`.
    for (const [name, dir] of pkgMap) {
      if (spec !== name && !spec.startsWith(name + '/')) continue
      const sub = spec === name ? '' : spec.slice(name.length + 1)
      const bases = sub ? [`${dir}/src/${sub}`, `${dir}/${sub}`] : [`${dir}/src/index`, `${dir}/index`, `${dir}/src`]
      for (const b of bases) {
        for (const cand of [`${b}.ts`, `${b}.tsx`, `${b}.mjs`, `${b}.js`, `${b}/index.ts`]) {
          if (trackedSet.has(cand)) return cand
        }
      }
      return null
    }
    return null
  }
  const importRe = /(?:import|export)[\s\S]*?from\s*['"]([^'"]+)['"]/g
  const nodeEdges = new Set() // "from|to"
  for (const f of tracked) {
    const fromNode = fileNode.get(f)
    if (!fromNode) continue
    const body = await readFile(`${repo}/${f}`, 'utf8')
    let m
    while ((m = importRe.exec(body))) {
      const target = resolveImport(f, m[1])
      if (!target) continue
      const toNode = fileNode.get(target)
      if (!toNode || toNode === fromNode) continue
      nodeEdges.add(`${fromNode}|${toNode}|${target}`)
    }
  }

  // Classify import-derived edges. persist and http edges are cross-boundary and
  // never appear in the relative-import graph, so they're carried over from the
  // current E, not derived here.
  // Precedence so a node->node edge aggregated from several file->file imports
  // of differing kinds resolves deterministically to the strongest.
  const RANK = { aggregate: 3, read: 2, flow: 1 }
  const derived = new Map() // "from|to" -> kind
  for (const key of nodeEdges) {
    const [from, to, target] = key.split('|')
    let kind
    if (aggregateFrom.has(from)) kind = 'aggregate'
    else if (readTargetRe.test(target)) kind = 'read'
    else kind = 'flow'
    const k = `${from}|${to}`
    const prev = derived.get(k)
    if (!prev || RANK[kind] > RANK[prev]) derived.set(k, kind)
  }

  const currentEdges = new Map(E.value.map(([f, t, k]) => [`${f}|${t}`, k]))
  const carried = [] // http/persist edges preserved from current E
  for (const [k, kind] of currentEdges) {
    if (kind === 'http' || kind === 'persist') carried.push([...k.split('|'), kind])
  }
  // Final edge set: carried cross-boundary edges + import-derived edges.
  const finalEdgeMap = new Map()
  for (const [f, t, k] of carried) finalEdgeMap.set(`${f}|${t}`, k)
  for (const [k, kind] of derived) if (!finalEdgeMap.has(k)) finalEdgeMap.set(k, kind)
  const newEdges = [...finalEdgeMap.entries()]
    .map(([k, kind]) => [...k.split('|'), kind])
    .sort((a, b) => (a[0] + a[1]).localeCompare(b[0] + b[1]))

  // ---- diff ----------------------------------------------------------------
  // Net-new edges (no prior from->to), kind-modified edges (from->to existed,
  // its kind changed), and deleted edges (a prior from->to now absent) are what
  // the highlighter draws; a from->to whose kind is unchanged is none of them.
  // http/persist are carried, never derived, so they're never "deleted".
  const edgesAdded = newEdges.filter(([f, t]) => !currentEdges.has(`${f}|${t}`))
  const edgesModified = newEdges.filter(([f, t, k]) => currentEdges.has(`${f}|${t}`) && currentEdges.get(`${f}|${t}`) !== k)
  const edgesDeleted = [...currentEdges].filter(([k, v]) => v !== 'http' && v !== 'persist' && !finalEdgeMap.has(k))
  const filesChanged = Object.keys(newFiles).filter((id) => JSON.stringify(newFiles[id]) !== JSON.stringify(FILES.value[id] || []))

  // ---- edited-node tier: content-only edits to already-mapped files ---------
  // Diff this branch against its merge-base with --base (default origin/main) and
  // map changed source files to their nodes, keeping only nodes not already
  // structural (added / filesChanged) — structure always wins. Same predicates as
  // enumeration, plus we drop the skill's own architecture.html sync commit.
  // Degrades to [] when the base ref, merge-base, or diff can't be computed (e.g.
  // origin/main unfetched in a cloud worktree); this step never fails the run.
  const structuralNodes = new Set(filesChanged)
  let editedNodes = []
  try {
    const mb = execFileSync('git', ['-C', repo, 'merge-base', 'HEAD', base], { encoding: 'utf8' }).trim()
    const edited = new Set()
    for (const f of execFileSync('git', ['-C', repo, 'diff', '--name-only', mb, 'HEAD'], { encoding: 'utf8' }).split('\n').filter(Boolean)) {
      if (!/\.(ts|tsx|mjs|js|css|html)$/.test(f) || isTest(f) || isIgnored(f) || f === 'docs/architecture.html') continue
      const id = fileNode.get(f)
      if (id && !structuralNodes.has(id)) edited.add(id)
    }
    editedNodes = [...edited].sort()
  } catch {
    editedNodes = []
  }

  const diff = {
    edgesAdded: edgesAdded.map(([f, t, k]) => `${f}->${t} (${k})`),
    edgesModified: edgesModified.map(([f, t, k]) => `${f}->${t} (${currentEdges.get(`${f}|${t}`)}->${k})`),
    edgesRemoved: edgesDeleted.map(([k]) => k.replace('|', '->')),
    // Machine-readable "from|to|kind" triples for highlight.mjs:
    //   edgesChanged -> --edges (drawn solid), edgesDeleted -> --removed (red dotted).
    edgesChanged: [...edgesAdded, ...edgesModified].map(([f, t, k]) => `${f}|${t}|${k}`),
    edgesDeleted: edgesDeleted.map(([k, v]) => `${k}|${v}`),
    filesChanged,
    editedNodes,
    nodesInN: Object.keys(N.value),
    unmapped,
  }

  const report = { repo, htmlPath, diff, newFilesCount: Object.keys(newFiles).length, edgeCount: newEdges.length }
  console.log(JSON.stringify(report, null, 2))

  if (doWrite) {
    const fmtFiles = fmtFilesBlock(newFiles)
    const fmtE = fmtEdgeBlock(newEdges)
    let out = html.slice(0, FILES.literalFrom) + fmtFiles + html.slice(FILES.literalTo)
    // recompute E offsets against original (edits above shift them) — re-extract
    const E2 = extractBlock(out, 'E')
    out = out.slice(0, E2.literalFrom) + fmtE + out.slice(E2.literalTo)
    await writeFile(htmlPath, out)
    console.error('wrote', htmlPath)
  }
}

function fmtFilesBlock(files) {
  const ids = Object.keys(files) // preserve N declaration order
  const lines = ids.map((id) => `  ${id}:[${files[id].map((f) => `'${f}'`).join(',')}],`)
  return `{\n${lines.join('\n')}\n}`
}
function fmtEdgeBlock(edges) {
  const lines = edges.map(([f, t, k]) => `  ['${f}','${t}','${k}'],`)
  return `[\n${lines.join('\n')}\n]`
}

main().catch((e) => { console.error(e); process.exit(1) })
