#!/usr/bin/env node
// The sanctioned image helper for screenshot evidence: info / crop / resize /
// compare / pair on PNGs. Pure JS (pngjs + pixelmatch), so it behaves the same in
// cloud and local with no system image tooling — no PIL, ImageMagick, or sips.
// Deps install on first use through ensure-deps.mjs, the same path record.mjs uses.
//
// Every op prints one JSON line on stdout (notes go to stderr). Exit 0 ok ·
// 1 compare's mismatch ratio is over --fail-above · 2 bad usage or input ·
// 3 deps couldn't install (`verifier-web: …` line names the failed step).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { DepsError, ensureDeps } from './ensure-deps.mjs'

const USAGE = `usage: image.mjs <op> ...
  info    <in.png>
  crop    <in.png> <out.png> --x <px> --y <px> --w <px> --h <px>
  resize  <in.png> <out.png> (--width <px> | --height <px> | --scale <factor>)
  compare <a.png> <b.png> [--diff <out.png>] [--threshold <0-1>] [--fit] [--fail-above <ratio>]
  pair    <a.png> <b.png> <out.png> [--height <px>] [--gap <px>]`

const BOOLEAN_FLAGS = new Set(['fit'])
const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47])

class UsageError extends Error {}

let PNG
let pixelmatch

function parse(argv) {
  const pos = []
  const flags = {}
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (!a.startsWith('--')) {
      pos.push(a)
      continue
    }
    const key = a.slice(2)
    if (BOOLEAN_FLAGS.has(key)) flags[key] = true
    else if (i + 1 < argv.length) flags[key] = argv[++i]
    else throw new UsageError(`--${key} needs a value`)
  }
  return { pos, flags }
}

function need(pos, names) {
  if (pos.length !== names.length) throw new UsageError(`expected ${names.join(' ')}, got ${pos.length} path(s)`)
  return pos
}

function num(flags, key, { min = 0, int = true, optional = false } = {}) {
  if (flags[key] === undefined) {
    if (optional) return undefined
    throw new UsageError(`--${key} is required`)
  }
  const n = Number(flags[key])
  if (!Number.isFinite(n) || n < min || (int && !Number.isInteger(n))) {
    throw new UsageError(`--${key} must be ${int ? 'an integer' : 'a number'} >= ${min}, got ${flags[key]}`)
  }
  return n
}

function read(path) {
  const abs = resolve(path)
  let buf
  try {
    buf = readFileSync(abs)
  } catch (e) {
    throw new UsageError(`can't read ${abs}: ${e.code ?? e.message}`)
  }
  if (!buf.subarray(0, 4).equals(PNG_MAGIC)) {
    throw new UsageError(`${abs} is not a PNG — capture screenshots as PNG (Playwright, \`xcrun simctl io booted screenshot\`, and Paper export all default to it)`)
  }
  let png
  try {
    png = PNG.sync.read(buf)
  } catch (e) {
    throw new UsageError(`${abs} didn't decode as PNG: ${e.message}`)
  }
  return { width: png.width, height: png.height, data: png.data, path: abs }
}

function write(img, path) {
  const abs = resolve(path)
  mkdirSync(dirname(abs), { recursive: true })
  const png = new PNG({ width: img.width, height: img.height })
  png.data = img.data
  writeFileSync(abs, PNG.sync.write(png))
  return abs
}

const dims = (img) => ({ path: img.path, width: img.width, height: img.height })

function blank(width, height) {
  return { width, height, data: Buffer.alloc(width * height * 4, 0xff) } // opaque white
}

function blit(dst, src, x, y) {
  for (let r = 0; r < src.height; r++) {
    src.data.copy(dst.data, ((y + r) * dst.width + x) * 4, r * src.width * 4, (r + 1) * src.width * 4)
  }
}

// Area-average resample: each output pixel averages the source pixels it covers,
// so a 3x simulator screenshot downscales without aliasing; upscaling degrades to
// nearest-neighbour. Evidence-grade, not print-grade.
function resample(img, width, height) {
  const { width: W, height: H, data } = img
  const out = Buffer.alloc(width * height * 4)
  for (let y = 0; y < height; y++) {
    const y0 = Math.floor((y * H) / height)
    const y1 = Math.max(y0 + 1, Math.floor(((y + 1) * H) / height))
    for (let x = 0; x < width; x++) {
      const x0 = Math.floor((x * W) / width)
      const x1 = Math.max(x0 + 1, Math.floor(((x + 1) * W) / width))
      const sum = [0, 0, 0, 0]
      for (let sy = y0; sy < y1; sy++) {
        for (let sx = x0; sx < x1; sx++) {
          const i = (sy * W + sx) * 4
          for (let c = 0; c < 4; c++) sum[c] += data[i + c]
        }
      }
      const n = (y1 - y0) * (x1 - x0)
      const o = (y * width + x) * 4
      for (let c = 0; c < 4; c++) out[o + c] = Math.round(sum[c] / n)
    }
  }
  return { width, height, data: out }
}

const toHeight = (img, height) => resample(img, Math.max(1, Math.round((img.width * height) / img.height)), height)

const OPS = {
  info(pos) {
    const [inPath] = need(pos, ['<in.png>'])
    return { op: 'info', ...dims(read(inPath)) }
  },

  crop(pos, flags) {
    const [inPath, outPath] = need(pos, ['<in.png>', '<out.png>'])
    const img = read(inPath)
    const x = num(flags, 'x')
    const y = num(flags, 'y')
    const w = num(flags, 'w', { min: 1 })
    const h = num(flags, 'h', { min: 1 })
    if (x + w > img.width || y + h > img.height) {
      throw new UsageError(`crop ${w}x${h}+${x}+${y} exceeds ${img.path} (${img.width}x${img.height})`)
    }
    const out = { width: w, height: h, data: Buffer.alloc(w * h * 4) }
    for (let r = 0; r < h; r++) {
      img.data.copy(out.data, r * w * 4, ((y + r) * img.width + x) * 4, ((y + r) * img.width + x + w) * 4)
    }
    return { op: 'crop', in: dims(img), out: write(out, outPath), width: w, height: h }
  },

  resize(pos, flags) {
    const [inPath, outPath] = need(pos, ['<in.png>', '<out.png>'])
    const img = read(inPath)
    const given = ['width', 'height', 'scale'].filter((k) => flags[k] !== undefined)
    if (given.length !== 1) throw new UsageError('resize takes exactly one of --width, --height, --scale')
    let width
    let height
    if (given[0] === 'width') {
      width = num(flags, 'width', { min: 1 })
      height = Math.round((img.height * width) / img.width)
    } else if (given[0] === 'height') {
      height = num(flags, 'height', { min: 1 })
      width = Math.round((img.width * height) / img.height)
    } else {
      const s = num(flags, 'scale', { int: false })
      width = Math.round(img.width * s)
      height = Math.round(img.height * s)
    }
    if (width < 1 || height < 1) throw new UsageError(`resize to ${width}x${height} is empty`)
    return { op: 'resize', in: dims(img), out: write(resample(img, width, height), outPath), width, height }
  },

  compare(pos, flags) {
    const [aPath, bPath] = need(pos, ['<a.png>', '<b.png>'])
    const a = read(aPath)
    let b = read(bPath)
    const threshold = num(flags, 'threshold', { int: false, optional: true }) ?? 0.1
    const failAbove = num(flags, 'fail-above', { int: false, optional: true })
    const result = { op: 'compare', a: dims(a), b: dims(b), width: a.width, height: a.height, threshold }
    if (a.width !== b.width || a.height !== b.height) {
      if (!flags.fit) {
        throw new UsageError(`sizes differ — a ${a.width}x${a.height}, b ${b.width}x${b.height}; crop/resize to matching regions first, or pass --fit to scale b onto a`)
      }
      const aspectDelta = Math.abs(a.width / a.height - b.width / b.height) / (a.width / a.height)
      if (aspectDelta > 0.01) {
        console.error(`image.mjs: --fit stretched b — aspect ratios differ by ${(aspectDelta * 100).toFixed(1)}%; crop both to the same region for a meaningful ratio`)
      }
      b = resample(b, a.width, a.height)
      Object.assign(result, { fitted: true, aspectDelta: Number(aspectDelta.toFixed(4)) })
    }
    const diff = flags.diff ? Buffer.alloc(a.width * a.height * 4) : null
    const mismatched = pixelmatch(a.data, b.data, diff, a.width, a.height, { threshold })
    const ratio = mismatched / (a.width * a.height)
    Object.assign(result, { mismatched, ratio: Number(ratio.toFixed(6)) })
    if (diff) result.diff = write({ width: a.width, height: a.height, data: diff }, flags.diff)
    if (failAbove !== undefined) Object.assign(result, { failAbove, exceeds: ratio > failAbove })
    return result
  },

  pair(pos, flags) {
    const [aPath, bPath, outPath] = need(pos, ['<a.png>', '<b.png>', '<out.png>'])
    const a = read(aPath)
    const b = read(bPath)
    const height = num(flags, 'height', { min: 1, optional: true }) ?? Math.min(a.height, b.height)
    const gap = num(flags, 'gap', { optional: true }) ?? 16
    const left = toHeight(a, height)
    const right = toHeight(b, height)
    const canvas = blank(left.width + gap + right.width, height)
    blit(canvas, left, 0, 0)
    blit(canvas, right, left.width + gap, 0)
    return { op: 'pair', a: dims(a), b: dims(b), out: write(canvas, outPath), width: canvas.width, height }
  },
}

const [op, ...rest] = process.argv.slice(2)
if (!Object.hasOwn(OPS, op ?? '')) {
  console.error(USAGE)
  process.exit(2)
}

try {
  const { pos, flags } = parse(rest)
  await ensureDeps()
  const pngjs = await import('pngjs')
  PNG = pngjs.PNG ?? pngjs.default.PNG
  pixelmatch = (await import('pixelmatch')).default
  const result = OPS[op](pos, flags)
  console.log(JSON.stringify(result))
  if (result.exceeds) process.exit(1)
} catch (e) {
  if (e instanceof DepsError) {
    console.error(`verifier-web: ${e.message}`)
    process.exit(3)
  }
  if (e instanceof UsageError) {
    console.error(`image.mjs: ${e.message}\n${USAGE}`)
    process.exit(2)
  }
  throw e
}
