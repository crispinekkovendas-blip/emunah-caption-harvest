/**
 * batch-salvage.mjs — publish the lessons the lanes translated but threw away (2026-11-15, the owner: "yes do
 * 1 and 2": rebuild the never-published lessons from the replies already saved in the repo, no Claude call).
 *
 *   node scripts/batch-salvage.mjs                      → video-batches/salvage-NNN/ (in/, out/, manifest.json, salvage.json)
 *   node scripts/batch-salvage.mjs --mark salvage-NNN   → after its publish: the lane batches still pending count
 *                                                          its published lessons as done (nothing of them is redone)
 *
 * Until 2026-11-08 a reply was read with a strict filter (a stray tab made a translated line "missing") and one
 * bad piece threw the whole lesson away; 268 lessons were translated two to four times and never published. Every
 * reply is still in video-batches/<batch>/out/<piece>.*.usage.json. Here, for each lesson no batch published,
 * every saved reply and every kept output is read the way scripts/batch-reply.mjs reads a new one (tolerantly,
 * only the piece's own range), and the latest good translation of each line wins. A lesson gets into the salvage
 * batch only when every line has one and its transcript still has the same lines: the Hebrew of every work file
 * is compared with the cues in Supabase. scripts/batch-publish.mjs then checks and publishes it like any batch.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIR = path.join(ROOT, 'video-batches')
const LANE_BATCH = /^(batch-\d{3}|lane\d+-\d{3})$/
const NAME_RE = new RegExp(['\\u05d9\\u05d4\\u05d5\\u05d4', '\\bYa?hweh\\b', '\\bJeh?ov[aá]h?\\b', '\\bJeov[aá]\\b', '\\bY-?H-?[WV]-?H\\b'].join('|'), 'i')
const readJSON = (f) => JSON.parse(fs.readFileSync(f, 'utf8'))
const output = (k, v) => {
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `${k}=${v}\n`)
  console.log(`${k}=${v}`)
}
const summary = (text) => {
  if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, text + '\n')
}

const batches = fs
  .readdirSync(DIR)
  .filter((d) => LANE_BATCH.test(d) && fs.existsSync(path.join(DIR, d, 'manifest.json')))
  .sort()
const manifests = new Map(batches.map((b) => [b, readJSON(path.join(DIR, b, 'manifest.json'))]))

/* ── --mark: the lane batches still pending take the salvaged lessons as done ─────────────────────────── */
if (process.argv.includes('--mark')) {
  const name = process.argv[process.argv.indexOf('--mark') + 1]
  const salvaged = new Set(readJSON(path.join(DIR, name, 'manifest.json')).done || [])
  for (const [b, m] of manifests) {
    if (m.status === 'done') continue
    const hit = m.lessons.map((l) => l.id).filter((id) => salvaged.has(id))
    if (!hit.length) continue
    m.done ||= []
    m.skipped ||= []
    m.salvaged = [...new Set([...(m.salvaged || []), ...hit])]
    for (const id of hit) if (!m.done.includes(id) && !m.skipped.includes(id)) m.done.push(id)
    if (m.lessons.every((l) => m.done.includes(l.id) || m.skipped.includes(l.id))) m.status = 'done'
    fs.writeFileSync(path.join(DIR, b, 'manifest.json'), JSON.stringify(m, null, 1) + '\n')
    console.log(`${b}: ${hit.length} lesson(s) published by ${name}${m.status === 'done' ? ' — batch done' : ''}`)
  }
  process.exit(0)
}

/* ── Supabase (read only here; batch-publish.mjs writes) ──────────────────────────────────────────────── */
const SUPA = (process.env.SUPABASE_URL || '').replace(/\/$/, '')
const H = { apikey: process.env.SUPABASE_SERVICE_KEY, authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY}` }
if (!SUPA) throw new Error('SUPABASE_URL missing')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function get(key) {
  for (let a = 1; ; a++) {
    try {
      const res = await fetch(`${SUPA}/rest/v1/global_options?select=value&key=eq.${encodeURIComponent(key)}`, { headers: H, signal: AbortSignal.timeout(60000) })
      if (!res.ok) throw new Error(`Supabase ${res.status}`)
      const row = (await res.json())[0]
      return row ? (typeof row.value === 'string' ? JSON.parse(row.value) : row.value) : null
    } catch (err) {
      if (a >= 4) throw err
      await sleep(5000 * a)
    }
  }
}

/* ── the lessons no batch published ───────────────────────────────────────────────────────────────────── */
const published = new Set()
for (const m of manifests.values()) for (const id of m.done || []) published.add(id)
const salvageDirs = fs.readdirSync(DIR).filter((d) => /^salvage-\d{3}$/.test(d))
for (const d of salvageDirs) {
  const f = path.join(DIR, d, 'manifest.json')
  if (fs.existsSync(f)) for (const id of readJSON(f).done || []) published.add(id)
}
const lessons = new Map()
for (const [b, m] of manifests)
  for (const l of m.lessons) {
    if (published.has(l.id)) continue
    if (!lessons.has(l.id)) lessons.set(l.id, { id: l.id, title: l.title, batches: [] })
    lessons.get(l.id).batches.push(b)
  }

/** a work file: its range and the Hebrew of each of its lines */
function work(b, piece) {
  const f = path.join(DIR, b, 'in', `${piece}.txt`)
  if (!fs.existsSync(f)) return null
  const t = fs.readFileSync(f, 'utf8').replace(/\r/g, '')
  const h = t.match(/traduzir as linhas (\d+) a (\d+)/)
  if (!h) return null
  const he = new Map()
  for (const l of (t.split('LINHAS A TRADUZIR:\n')[1] || '').split('\n')) {
    const m = l.match(/^(\d+)\|[^|]*\|(.*)$/)
    if (m) he.set(Number(m[1]), m[2])
  }
  return { from: Number(h[1]), to: Number(h[2]), he }
}

/** the good lines of one reply, read as scripts/batch-reply.mjs reads them (a stray tab, a line split in two) */
function goodLines(text, from, to) {
  const rows = []
  for (const raw of String(text || '').replace(/\r/g, '').split('\n')) {
    const line = raw.replace(/\s+$/, '')
    if (!line.trim()) continue
    const m = line.match(/^(\d+)\t(.+)$/)
    if (m) {
      const texts = m[2].split('\t').map((x) => x.trim()).filter(Boolean)
      // a column copied from the work file in front of the translation: the clock, or the number again
      if (texts.length === 3 && (/^\d{1,2}:\d{2}(?::\d{2})?$/.test(texts[0]) || texts[0] === m[1])) texts.shift()
      rows.push({ n: Number(m[1]), texts })
    }
    else if (/^\t/.test(line) && rows.length && rows[rows.length - 1].texts.length === 1)
      rows[rows.length - 1].texts.push(...line.split('\t').map((x) => x.trim()).filter(Boolean)) // its own tabs split too
  }
  const out = new Map()
  for (const { n, texts } of rows) if (n >= from && n <= to && texts.length === 2 && !out.has(n) && !NAME_RE.test(texts.join(' '))) out.set(n, texts)
  return out
}

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\-]/g, '\\$&')
const norm = (s) => String(s || '').split('\n')[0].replace(/\s+/g, ' ').trim()

/** every saved reply and kept output of a lesson, oldest first: { order, he (its work file's Hebrew), lines } */
function sources(lesson) {
  const list = []
  for (const b of lesson.batches) {
    const created = manifests.get(b).created || ''
    const outDir = path.join(DIR, b, 'out')
    if (!fs.existsSync(outDir)) continue
    const re = new RegExp(`^(${esc(lesson.id)}\\.p\\d+)(?:\\.(.+?))?\\.(usage\\.json|txt)$`)
    for (const f of fs.readdirSync(outDir)) {
      const m = f.match(re)
      if (!m) continue
      const [, piece, tag = '', kind] = m
      if (/-pt$/.test(tag)) continue // the Portuguese-only call: its merge is in the kept output
      const w = work(b, piece)
      if (!w) continue
      let text = ''
      if (kind === 'txt') text = fs.readFileSync(path.join(outDir, f), 'utf8')
      else {
        try {
          const j = readJSON(path.join(outDir, f))
          if (j.is_error) continue
          text = j.result
        } catch {
          continue
        }
      }
      const t = tag.match(/^r(\d+)-(\d+)(?:-(\d+))?/)
      // a kept output is the batch's final word on its piece: after every reply of that batch
      const order = [created, kind === 'txt' ? Infinity : t ? Number(t[1]) : 0, t ? Number(t[2]) : 0, t ? Number(t[3] || 0) : 0]
      list.push({ order, he: w.he, lines: goodLines(text, w.from, w.to) })
    }
  }
  list.sort((x, y) => {
    for (let k = 0; k < 4; k++) if (x.order[k] !== y.order[k]) return x.order[k] < y.order[k] ? -1 : 1
    return 0
  })
  return list
}

/**
 * a lesson with gaps, still open in a lane batch: every piece of it whose lines all have a saved good translation
 * gets its output file, so the lane translates only the pieces with real gaps (2026-11-15: 0g-eVAkDRJM lacks 1 of
 * 1,532 lines, yet all 13 of its pieces were waiting to be translated again)
 */
function fill(lesson, tr) {
  const done = []
  for (const b of lesson.batches) {
    const m = manifests.get(b)
    if (m.status === 'done' || (m.done || []).includes(lesson.id) || (m.skipped || []).includes(lesson.id)) continue
    for (const c of m.chunks) {
      if (c.replace(/\.p\d+$/, '') !== lesson.id) continue
      const f = path.join(DIR, b, 'out', `${c}.txt`)
      if (fs.existsSync(f)) continue
      const w = work(b, c)
      if (!w) continue
      const lines = []
      for (let i = w.from; i <= w.to; i++) {
        if (!tr.has(i)) break
        lines.push(`${i}\t${tr.get(i)[0]}\t${tr.get(i)[1]}`)
      }
      if (lines.length !== w.to - w.from + 1) continue
      fs.writeFileSync(f, lines.join('\n') + '\n')
      done.push(`${b}/${c}`)
    }
  }
  return done
}

/* ── rebuild ───────────────────────────────────────────────────────────────────────────────────────────── */
const name = `salvage-${String(salvageDirs.length + 1).padStart(3, '0')}`
const OUT = path.join(DIR, name)
const result = { name, created: new Date().toISOString(), looked: lessons.size, salvaged: [], filled: [], incomplete: [], changed: [], elsewhere: [], errors: [] }
const ready = []
let k = 0
for (const lesson of lessons.values()) {
  k++
  const list = sources(lesson)
  let doc
  let en
  try {
    doc = await get(`videos/transcript/${lesson.id}`)
    en = await get(`videos/transcript/${lesson.id}/en`)
  } catch (err) {
    result.errors.push({ id: lesson.id, why: String(err?.message || err) })
    continue
  }
  if (en?.by) {
    result.elsewhere.push({ id: lesson.id, by: en.by })
    continue
  }
  const n = doc?.cues?.length || 0
  if (!n || doc.lang !== 'he') {
    result.changed.push({ id: lesson.id, why: n ? `lang ${doc.lang}` : 'no transcript' })
    continue
  }
  // a reply counts only when the transcript still has the Hebrew its work file had, line for line (a lesson
  // transcribed again since has other lines under the same numbers)
  const valid = list.filter((s) => [...s.he].every(([i, t]) => i < n && norm(t) === norm(doc.cues[i][2])))
  const stale = list.length - valid.length
  const tr = new Map()
  for (const s of valid) for (const [i, texts] of s.lines) tr.set(i, texts) // the latest good translation wins
  const missing = []
  for (let i = 0; i < n; i++) if (!tr.has(i)) missing.push(i)
  if (missing.length) {
    const filled = fill(lesson, tr)
    if (filled.length) result.filled.push({ id: lesson.id, pieces: filled })
    if (stale) result.changed.push({ id: lesson.id, why: `${stale} of ${list.length} replies were made on other Hebrew lines; ${missing.length} of ${n} lines left` })
    else result.incomplete.push({ id: lesson.id, lines: n, missing: missing.length, first: missing.slice(0, 8) })
    continue
  }
  ready.push({ lesson, n, tr })
  result.salvaged.push({ id: lesson.id, lines: n, replies: valid.length, stale, batches: lesson.batches })
  if (k % 25 === 0) console.log(`${k} / ${lessons.size} looked at, ${ready.length} ready`)
}

if (ready.length) {
  fs.mkdirSync(path.join(OUT, 'in'), { recursive: true })
  fs.mkdirSync(path.join(OUT, 'out'), { recursive: true })
  for (const { lesson, n, tr } of ready) {
    fs.writeFileSync(
      path.join(OUT, 'in', `${lesson.id}.p0.txt`),
      [
        `videoId: ${lesson.id}`,
        `parte 1 de 1 · traduzir as linhas 0 a ${n - 1} (${n} linhas)`,
        '',
        `(${result.created.slice(0, 10)}: rebuilt from the replies the lanes saved in ${lesson.batches.join(', ')} — no new translation)`,
      ].join('\n') + '\n',
    )
    const lines = []
    for (let i = 0; i < n; i++) lines.push(`${i}\t${tr.get(i)[0]}\t${tr.get(i)[1]}`)
    fs.writeFileSync(path.join(OUT, 'out', `${lesson.id}.p0.txt`), lines.join('\n') + '\n')
  }
  const manifest = {
    name,
    lane: 0,
    salvage: true,
    created: result.created,
    status: 'pending',
    lessons: ready.map(({ lesson, n }) => ({ id: lesson.id, title: lesson.title, lines: n, parts: 1, from: 'salvage', sources: lesson.batches })),
    chunks: ready.map(({ lesson }) => `${lesson.id}.p0`),
  }
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n')
  fs.writeFileSync(path.join(OUT, 'salvage.json'), JSON.stringify(result, null, 1) + '\n')
}

const lines = ready.reduce((s, r) => s + r.n, 0)
console.log(
  `\n${lessons.size} lessons never published: ${ready.length} rebuilt whole (${lines} lines), ${result.incomplete.length} with lines no reply translated, ` +
    `${result.changed.length} whose transcript changed, ${result.elsewhere.length} already translated since, ${result.errors.length} Supabase errors`,
)
const pieces = result.filled.reduce((s, x) => s + x.pieces.length, 0)
console.log(`pieces of lessons with gaps filled from saved replies (the lanes skip them): ${pieces} in ${result.filled.length} lessons`)
for (const x of result.filled) console.log(`  filled     ${x.id}: ${x.pieces.join(' ')}`)
for (const x of result.incomplete) console.log(`  incomplete ${x.id}: ${x.missing} of ${x.lines} lines missing (${x.first.join(', ')}…)`)
for (const x of result.changed) console.log(`  changed    ${x.id}: ${x.why}`)
for (const x of result.errors) console.log(`  error      ${x.id}: ${x.why}`)
summary(
  [
    `## ${name}`,
    '',
    '| | lessons |',
    '|---|---|',
    `| never published (looked at) | ${lessons.size} |`,
    `| **rebuilt whole from saved replies** | **${ready.length}** (${lines} lines) |`,
    `| with gaps: pieces filled in their lane batch | ${result.filled.length} (${pieces} pieces) |`,
    `| lines no saved reply translated | ${result.incomplete.length} |`,
    `| transcript changed since | ${result.changed.length} |`,
    `| already translated since | ${result.elsewhere.length} |`,
    `| Supabase errors | ${result.errors.length} |`,
  ].join('\n'),
)
output('batch', name)
output('count', String(ready.length))
output('filled', String(pieces))
