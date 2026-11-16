/**
 * batch-repair.mjs — translate again the published lines that came from a block Claude took back (2026-11-15, the
 * owner: "yes do the repair of the 350 lessons too").
 *
 *   node scripts/batch-repair.mjs           dry run: the plan → out/repair-plan.json and the step summary (nothing else)
 *   node scripts/batch-repair.mjs --write   one repair batch per lane: video-batches/lane<L>-9NN/
 *
 * 1,605 saved replies hold a note in which Claude takes back what it had just written ("Wait — my numbering above
 * drifted", "Hmm — I need to correct…"); the readers before 2026-11-15 kept those lines, and the ten-lane test showed
 * them live, one line or more out of step with the Hebrew. Here every such reply is read again: the lines written
 * before its last note are candidates; a published line (videos/transcript/<id>/en and /pt) whose English AND
 * Portuguese are exactly a candidate's is taken back — unless the same reply wrote it again, the same, after the note.
 *
 * Each lesson with such lines gets work files exactly as scripts/batch-make.mjs writes them (120 lines, the study as
 * context). A piece without a taken-back line gets its out/ file from the published text (nothing asked); a piece with
 * some gets out/<piece>.partial.json holding all its other lines, so the lane asks Claude ONLY for the taken-back
 * ones (translate-batch.yml, merged.retry.txt). scripts/batch-publish.mjs then checks and publishes the lesson as always.
 * The batches are named lane<L>-901, -902…: a lane resumes them like its own, after the batch it is working on.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { readReply, RETRACT } from './reply-lines.mjs'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIR = path.join(ROOT, 'video-batches')
const WRITE = process.argv.includes('--write')
const LANES = 20 // as scripts/batch-make.mjs
const CHUNK = 120
const BEFORE = 12
const LANE_BATCH = /^(batch-\d{3}|lane\d+-\d{3})$/
const laneOf = (id) => [...id].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7) % LANES
const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim()
const clock = (s) => {
  s = Math.floor(s)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const x = s % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}`
}
const output = (k, v) => {
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `${k}=${v}\n`)
  console.log(`${k}=${v}`)
}
const summary = (text) => {
  if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, text + '\n')
}

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

/* ── 1. the replies that take lines back ─────────────────────────────────────────────────────────────────── */
const dirs = fs.readdirSync(DIR).filter((d) => LANE_BATCH.test(d)).sort()
const manifests = new Map(dirs.map((d) => [d, JSON.parse(fs.readFileSync(path.join(DIR, d, 'manifest.json'), 'utf8'))]))
// lessons a lane is still working on are left alone (their lines are not published yet, or are being redone)
const busy = new Set()
for (const m of manifests.values()) {
  if (m.status === 'done') continue
  for (const l of m.lessons) if (!(m.done || []).includes(l.id) && !(m.skipped || []).includes(l.id)) busy.add(l.id)
}
const cand = new Map() // id → [{ rows: Map<n, [[en, pt], …]>, redo: Map<n, [en, pt]> }]
let replies = 0
let withNote = 0
for (const b of dirs) {
  const out = path.join(DIR, b, 'out')
  if (!fs.existsSync(out)) continue
  for (const f of fs.readdirSync(out).filter((x) => x.endsWith('.usage.json') && !x.includes('-pt.'))) {
    let j
    try {
      j = JSON.parse(fs.readFileSync(path.join(out, f), 'utf8'))
    } catch {
      continue
    }
    if (j.num_turns !== 1 || j.is_error || !j.result) continue
    replies++
    const text = String(j.result).replace(/\r/g, '')
    const lines = text.split('\n')
    let last = -1
    let rowSeen = false
    lines.forEach((l, i) => {
      if (/^\d+[\t|]/.test(l)) rowSeen = true
      else if (rowSeen && l.trim() && RETRACT.test(l.trim())) last = i
    })
    if (last < 0) continue
    const piece = f.replace(/\.r\d.*$/, '').replace(/\.usage\.json$/, '')
    const inF = path.join(DIR, b, 'in', `${piece}.txt`)
    if (!fs.existsSync(inF)) continue
    const h = fs.readFileSync(inF, 'utf8').match(/traduzir as linhas (\d+) a (\d+)/)
    if (!h) continue
    withNote++
    const a = Number(h[1])
    const z = Number(h[2])
    const before = lines.slice(0, last)
    const rows = new Map()
    const add = (n, t) => {
      if (!rows.has(n)) rows.set(n, [])
      rows.get(n).push(t)
    }
    // what the old readers could have kept: the block-aware reading, and every line on its own (a doubled line)
    for (const [n, t] of readReply(before.join('\n'), a, z).good) add(n, t)
    for (const l of before) for (const [n, t] of readReply(l, a, z).good) add(n, t)
    const id = piece.replace(/\.p\d+$/, '')
    if (!cand.has(id)) cand.set(id, [])
    cand.get(id).push({ rows, redo: readReply(text, a, z).good })
  }
}
console.log(`${replies} replies read, ${withNote} take lines back, in ${cand.size} lessons`)
// the same lessons' CLEAN replies (no taking-back note): a published line one of them also wrote, word for word, is
// not only from a block taken back — two separate translations agree on it, so it stays (the dry run of 2026-11-15
// flagged 30 lines of jrgUrbDQwqY that its clean re-translation had written identically)
const clean = new Map() // id → Set of "n␟en␟pt"
for (const b of dirs) {
  const out = path.join(DIR, b, 'out')
  if (!fs.existsSync(out)) continue
  for (const f of fs.readdirSync(out).filter((x) => x.endsWith('.usage.json') && !x.includes('-pt.'))) {
    const piece = f.replace(/\.r\d.*$/, '').replace(/\.usage\.json$/, '')
    const id = piece.replace(/\.p\d+$/, '')
    if (!cand.has(id)) continue
    let j
    try {
      j = JSON.parse(fs.readFileSync(path.join(out, f), 'utf8'))
    } catch {
      continue
    }
    if (j.num_turns !== 1 || j.is_error || !j.result) continue
    const text = String(j.result).replace(/\r/g, '')
    let rowSeen = false
    const takesBack = text.split('\n').some((l) => {
      if (/^\d+[\t|]/.test(l)) rowSeen = true
      else if (rowSeen && l.trim() && RETRACT.test(l.trim())) return true
      return false
    })
    if (takesBack) continue
    const inF = path.join(DIR, b, 'in', `${piece}.txt`)
    if (!fs.existsSync(inF)) continue
    const h = fs.readFileSync(inF, 'utf8').match(/traduzir as linhas (\d+) a (\d+)/)
    if (!h) continue
    if (!clean.has(id)) clean.set(id, new Set())
    for (const [n, [e, p]] of readReply(text, Number(h[1]), Number(h[2])).good) clean.get(id).add(`${n}␟${norm(e)}␟${norm(p)}`)
  }
}

/* ── 2. which of those lines are live ────────────────────────────────────────────────────────────────────── */
const plan = []
const skipped = { busy: 0, notClaude: 0, changed: 0, clean: 0, errors: 0 }
let agreed = 0 // live lines a clean reply also wrote, word for word
let k = 0
for (const [id, list] of cand) {
  if (++k % 50 === 0) console.log(`${k} / ${cand.size} lessons looked at, ${plan.length} to repair`)
  if (busy.has(id)) {
    skipped.busy++
    continue
  }
  let en, pt, doc
  try {
    en = await get(`videos/transcript/${id}/en`)
    if (!en?.by) {
      skipped.notClaude++
      continue
    }
    pt = await get(`videos/transcript/${id}/pt`)
    doc = await get(`videos/transcript/${id}`)
  } catch (err) {
    skipped.errors++
    console.log(`  error ${id}: ${String(err?.message || err)}`)
    continue
  }
  const n = doc?.cues?.length || 0
  if (!n || en.texts?.length !== n || pt?.texts?.length !== n) {
    skipped.changed++
    continue
  }
  const bad = new Set()
  for (const { rows, redo } of list)
    for (const [i, texts] of rows) {
      if (i >= n || bad.has(i)) continue
      const E = norm(en.texts[i])
      const P = norm(pt.texts[i])
      if (!texts.some(([e, p]) => norm(e) === E && norm(p) === P)) continue
      const r = redo.get(i)
      if (r && norm(r[0]) === E && norm(r[1]) === P) continue // written again, the same, after the note
      if (clean.get(id)?.has(`${i}␟${E}␟${P}`)) {
        agreed++
        continue
      }
      bad.add(i)
    }
  if (!bad.size) {
    skipped.clean++
    continue
  }
  plan.push({ id, title: doc.title, lines: n, bad: [...bad].sort((x, y) => x - y), doc, en: en.texts, pt: pt.texts })
}
const badLines = plan.reduce((s, x) => s + x.bad.length, 0)
const askPieces = plan.reduce((s, x) => s + new Set(x.bad.map((i) => Math.floor(i / CHUNK))).size, 0)
// the ten-lane test: ~68 output tokens a line (thinking included), ~8k input tokens a request, Sonnet 5.5 list prices
const usd = (badLines * 68 * 10 + askPieces * 8000 * 2) / 1e6
console.log(`to repair: ${plan.length} lessons, ${badLines} lines, ${askPieces} pieces to ask (≈ $${usd.toFixed(0)} list price)`)
console.log(`left alone: ${JSON.stringify(skipped)} · ${agreed} live lines kept because a clean reply wrote them the same`)
fs.mkdirSync(path.join(ROOT, 'out'), { recursive: true })
fs.writeFileSync(
  path.join(ROOT, 'out', 'repair-plan.json'),
  JSON.stringify({ replies, withNote, lessons: plan.length, lines: badLines, pieces: askPieces, usd: Math.round(usd), skipped, agreed, plan: plan.map(({ id, title, lines, bad }) => ({ id, title, lines, bad })) }, null, 1),
)

/* ── 3. the repair batches ──────────────────────────────────────────────────────────────────────────────── */
const perLane = new Map()
for (const x of plan) {
  const lane = laneOf(x.id) + 1
  if (!perLane.has(lane)) perLane.set(lane, [])
  perLane.get(lane).push(x)
}
const made = []
if (WRITE)
  for (const [lane, list] of [...perLane].sort((a, b) => a[0] - b[0])) {
    let nnn = 901
    while (fs.existsSync(path.join(DIR, `lane${lane}-${nnn}`))) nnn++
    const name = `lane${lane}-${nnn}`
    fs.mkdirSync(path.join(DIR, name, 'in'), { recursive: true })
    fs.mkdirSync(path.join(DIR, name, 'out'), { recursive: true })
    fs.writeFileSync(path.join(DIR, name, 'out', '.keep'), '')
    const lessons = []
    const chunks = []
    let asked = 0
    for (const { id, doc, en, pt, bad } of list) {
      const n = doc.cues.length
      const badSet = new Set(bad)
      const studyText = [
        `TÍTULO DO ESTUDO: ${doc.title}`,
        `RESUMO: ${doc.summary}`,
        `MOMENTOS: ${(doc.moments || []).map((m) => `${clock(m[0])} ${m[1]}`).join(' · ')}`,
        `FONTES CITADAS: ${(doc.sources || []).map((s) => `${clock(s[0])} ${s[2]}`).join(' · ')}`,
      ].join('\n')
      const line = (i) => `${i}|${clock(doc.cues[i][0])}|${doc.cues[i][2]}`
      const parts = Math.ceil(n / CHUNK)
      for (let p = 0; p < parts; p++) {
        const a = p * CHUNK
        const b = Math.min(n, a + CHUNK) - 1
        const before = []
        for (let i = Math.max(0, a - BEFORE); i < a; i++) before.push(line(i))
        const body = []
        for (let i = a; i <= b; i++) body.push(line(i))
        const piece = `${id}.p${p}`
        fs.writeFileSync(
          path.join(DIR, name, 'in', `${piece}.txt`),
          [
            `videoId: ${id}`,
            `parte ${p + 1} de ${parts} · traduzir as linhas ${a} a ${b} (${b - a + 1} linhas)`,
            '',
            'ESTUDO DA AULA (contexto — já revisado, use para nomes, versículos e termos):',
            studyText,
            '',
            ...(before.length ? ['LINHAS ANTERIORES (só contexto, NÃO traduzir):', ...before, ''] : []),
            'LINHAS A TRADUZIR:',
            ...body,
          ].join('\n') + '\n',
        )
        chunks.push(piece)
        const keep = []
        for (let i = a; i <= b; i++) if (!badSet.has(i)) keep.push([i, [String(en[i] ?? '').trim(), String(pt[i] ?? '').trim()]])
        if (keep.length === b - a + 1) {
          // nothing taken back here: the published lines, as they are
          fs.writeFileSync(path.join(DIR, name, 'out', `${piece}.txt`), keep.map(([i, [e, q]]) => `${i}\t${e}\t${q}`).join('\n') + '\n')
        } else {
          asked++
          if (keep.length) fs.writeFileSync(path.join(DIR, name, 'out', `${piece}.partial.json`), JSON.stringify(keep))
        }
      }
      lessons.push({ id, title: doc.title, lines: n, parts, from: 'reparo', repair: bad.length })
    }
    fs.writeFileSync(
      path.join(DIR, name, 'manifest.json'),
      JSON.stringify(
        {
          name,
          lane,
          created: new Date().toISOString(),
          status: 'pending',
          repair: 'lines taken back by Claude in its own reply, translated again (scripts/batch-repair.mjs)',
          repairLines: Object.fromEntries(list.map((x) => [x.id, x.bad])),
          lessons,
          chunks,
        },
        null,
        1,
      ) + '\n',
    )
    made.push(`${name}: ${lessons.length} lessons, ${asked} pieces to ask`)
    console.log(`  ${made[made.length - 1]}`)
  }

summary(
  [
    `## Repair of the lines Claude took back${WRITE ? '' : ' (dry run)'}`,
    '',
    `${replies} saved replies read · ${withNote} take lines back · in ${cand.size} lessons`,
    '',
    '| | |',
    '|---|---|',
    `| lessons to repair | **${plan.length}** |`,
    `| taken-back lines live | **${badLines}** |`,
    `| pieces to ask Claude (only those lines) | ${askPieces} |`,
    `| estimate (list price) | ≈ $${usd.toFixed(0)} |`,
    `| left alone: still in a lane / not Claude's / transcript changed / no live line / errors | ${skipped.busy} / ${skipped.notClaude} / ${skipped.changed} / ${skipped.clean} / ${skipped.errors} |`,
    `| live lines kept because a clean reply wrote them the same | ${agreed} |`,
    ...(made.length ? ['', ...made.map((m) => `- ${m}`)] : []),
  ].join('\n'),
)
output('lessons', String(plan.length))
output('batches', String(made.length))
