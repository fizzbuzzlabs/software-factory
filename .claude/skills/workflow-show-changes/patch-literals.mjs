#!/usr/bin/env node
// Applies the agent's judgment edits (step 3) to the N, ELI5, LAYERS and E literals
// of docs/architecture.html, for a sync whose target is another worktree, where
// the Edit tool is refused. Every edit is an exact-match replacement that must
// hit once inside its named literal, so the surrounding shell can't be touched.
// All-or-nothing: any failed edit exits 1 and writes nothing. FILES is off limits:
// only derive.mjs --write changes it.
//
//   node patch-literals.mjs --html <path> --edits <edits.json>
//
// edits.json: [{ "literal": "N" | "ELI5" | "LAYERS" | "E", "old": "<text>", "new": "<text>" }, ...]
import { readFile, writeFile } from 'node:fs/promises'

const EDITABLE = new Set(['N', 'ELI5', 'LAYERS', 'E'])

function argValue(name) {
  const i = process.argv.indexOf(`--${name}`)
  return i >= 0 ? process.argv[i + 1] : undefined
}

// Same scan as derive.mjs's extractBlock: the span of `const NAME = <literal>`.
function literalSpan(src, name) {
  const m = src.match(new RegExp(`const\\s+${name}\\s*=\\s*`))
  if (!m) return null
  const start = m.index + m[0].length
  const open = src[start]
  const close = open === '{' ? '}' : open === '[' ? ']' : null
  if (!close) return null
  let depth = 0, inStr = null
  for (let i = start; i < src.length; i++) {
    const c = src[i]
    if (inStr) { if (c === '\\') i++; else if (c === inStr) inStr = null; continue }
    if (c === "'" || c === '"' || c === '`') { inStr = c; continue }
    if (c === open) depth++
    else if (c === close && --depth === 0) return { from: start, to: i + 1 }
  }
  return null
}

function applyEdit(html, { literal, old, new: next }, label) {
  if (!EDITABLE.has(literal)) throw new Error(`${label}: literal must be N, ELI5, LAYERS or E, got ${literal}`)
  if (typeof old !== 'string' || !old || typeof next !== 'string') throw new Error(`${label}: needs non-empty "old" and a string "new"`)

  const span = literalSpan(html, literal)
  if (!span) throw new Error(`${label}: could not locate the ${literal} literal`)

  const body = html.slice(span.from, span.to)
  const hits = body.split(old).length - 1
  if (hits !== 1) throw new Error(`${label}: "old" must match once inside ${literal}, matched ${hits} times`)

  const patched = html.slice(0, span.from) + body.replace(old, () => next) + html.slice(span.to)

  // The literal must still close exactly where the new text says it does, and
  // still parse; otherwise the edit broke out of it into the shell.
  const after = literalSpan(patched, literal)
  if (!after || after.to !== span.to + next.length - old.length) throw new Error(`${label}: the edit changes where ${literal} closes`)
  try {
    new Function(`return (${patched.slice(after.from, after.to)})`)()
  } catch (e) {
    throw new Error(`${label}: ${literal} no longer parses: ${e.message}`)
  }
  return patched
}

async function main() {
  const htmlPath = argValue('html')
  const editsPath = argValue('edits')
  if (!htmlPath || !editsPath) throw new Error('usage: patch-literals.mjs --html <path> --edits <edits.json>')

  const edits = JSON.parse(await readFile(editsPath, 'utf8'))
  if (!Array.isArray(edits) || !edits.length) throw new Error('edits must be a non-empty array')

  const html = await readFile(htmlPath, 'utf8')
  const out = edits.reduce((acc, edit, i) => applyEdit(acc, edit, `edit ${i}`), html)
  await writeFile(htmlPath, out)
  console.log(JSON.stringify({ htmlPath, applied: edits.length }))
}

main().catch((e) => { console.error(e.message); process.exit(1) })
