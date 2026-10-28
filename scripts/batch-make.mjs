/**
 * batch-make.mjs — the next batch of lessons for Claude to translate (video-batches/batch-NNN/).
 *
 *   node --experimental-transform-types --import ./scripts/ts-hook.mjs scripts/batch-make.mjs [--size 25]
 *
 * If a batch is still pending (some chunks without output), it is resumed: nothing new is made and
 * the chunks still to translate are listed. Otherwise the next batch is built from Supabase: the
 * week's parashá first (hebcal), then the richest Hebrew lessons (most sources), skipping lessons
 * already in a batch or already translated by Claude. Each lesson is split into chunks of ≤ CHUNK
 * lines with the lesson's study as context — the work files the agents read.
 *
 * --lane N: each lane resumes only its own pending batch and owns the batches it makes; lessons are never
 * shared — every batch, whatever its lane, counts as taken.
 *
 * Writes GITHUB_OUTPUT: batch=<name> and chunks=<JSON list of "<id>.p<k>"> (empty when nothing is left).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parashiot } from '../src/data/parashiot.ts'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIR = path.join(ROOT, 'video-batches')
const SITE = process.env.SITE_URL || 'https://emunah-shlemah-qwik.vercel.app'
const SIZE = Number(process.argv[process.argv.indexOf('--size') + 1]) || 25
// lanes (2026-10-11): several batches run at the same time, each owned by one lane; a batch made
// before lanes existed belongs to lane 1
const LANE = Number(process.argv[process.argv.indexOf('--lane') + 1]) || 1
// 2026-10-15: 450 → 120 lines per request. With 450 Claude dropped or doubled lines (119 lessons skipped
// after 3 tries) and let the text slide up to 6 lines ahead of the Hebrew (subtitles before the voice)
const CHUNK = 120
const BEFORE = 12
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
const output = (k, v) => {
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `${k}=${v}\n`)
  console.log(`${k}=${v}`)
}
const clock = (s) => {
  s = Math.floor(s)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const x = s % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}`
}
/** chunks of a batch that have no output yet */
const pending = (name) => {
  const m = JSON.parse(fs.readFileSync(path.join(DIR, name, 'manifest.json'), 'utf8'))
  return m.chunks.filter((c) => !fs.existsSync(path.join(DIR, name, 'out', `${c}.txt`)))
}

fs.mkdirSync(DIR, { recursive: true })
const batches = fs.readdirSync(DIR).filter((d) => /^(batch-\d{3}|lane\d+-\d{3})$/.test(d)).sort()

// 1. an unfinished batch is resumed
for (const b of batches) {
  const m = JSON.parse(fs.readFileSync(path.join(DIR, b, 'manifest.json'), 'utf8'))
  if (m.status === 'done' || (m.lane || 1) !== LANE) continue
  const left = pending(b)
  console.log(`${b} is still pending: ${left.length} chunks without output`)
  output('batch', b)
  output('chunks', JSON.stringify(left))
  process.exit(0)
}

// 2. otherwise the next batch
const taken = new Set()
// a lesson skipped in a batch made with the old 450-line requests gets one more chance (2026-10-15)
// 2026-10-28 (the owner: "keep doing the transcription work non stop"): a lesson skipped with 120-line
// requests (Claude dropped or doubled lines) gets one more chance in SMALL pieces; skipped again, it stays
const SMALL = 40
const small = new Set()
for (const b of batches) {
  const m = JSON.parse(fs.readFileSync(path.join(DIR, b, 'manifest.json'), 'utf8'))
  const old = m.created && m.created < '2026-10-15T12:00'
  const again = new Set((m.skipped || []).filter((id) => old || !m.lessons.find((l) => l.id === id)?.small))
  for (const l of m.lessons) if (!again.has(l.id)) taken.add(l.id)
  if (!old) for (const id of again) small.add(id)
}
const study = (await (await fetch(`${SITE}/data/videos/study.json`, { signal: AbortSignal.timeout(60000) })).json()).study

// the week's parashá (hebcal, São Paulo) → its lessons first
let week = []
try {
  const hc = await (await fetch('https://www.hebcal.com/shabbat?cfg=json&geonameid=3448439&M=on', { signal: AbortSignal.timeout(30000) })).json()
  const title = (hc.items || []).find((i) => i.category === 'parashat')?.title?.replace(/^Parashat\s+/, '') || ''
  const names = title.split('-')
  const keys = parashiot.filter((p) => names.some((n) => [p.name, ...(p.hebcalNames || [])].includes(n.trim()))).map((p) => p.key)
  for (const k of keys) {
    const r = await fetch(`${SITE}/data/videos/shiurim/${k}.json`, { signal: AbortSignal.timeout(30000) })
    if (r.ok) week.push(...(await r.json()).lessons.map((l) => l.id))
  }
  console.log(`the week's parashá: ${title || '?'} (${week.length} lessons)`)
} catch (err) {
  console.log(`hebcal: ${String(err?.message || err)} — richest lessons only`)
}
// 2026-10-28 (the owner: "put the newest first"): lessons uploaded in the last 60 days lead, newest
// first, so a lesson the daily pipeline curated reaches Shiur Hebraico within hours; the upload dates come
// from the library seeds the site publishes
const fresh = []
try {
  const since = new Date(Date.now() - 60 * 86400_000).toISOString()
  const dates = new Map()
  for (const seed of ['he', 'kabala']) {
    const r = await fetch(`${SITE}/data/videos/${seed}.json`, { signal: AbortSignal.timeout(60000) })
    if (r.ok) for (const v of (await r.json()).videos || []) if (v.published) dates.set(v.videoId, v.published)
  }
  fresh.push(...[...dates].filter(([id, p]) => study[id] && p >= since).sort((a, b) => b[1].localeCompare(a[1])).map(([id]) => id))
  console.log(`uploaded in the last 60 days: ${fresh.length} lessons with a study`)
} catch (err) {
  console.log(`seeds: ${String(err?.message || err)} — no newest-first list`)
}
const richest = Object.entries(study)
  .sort((a, b) => b[1].s - a[1].s || b[1].q - a[1].q)
  .map(([id]) => id)
// each lane owns a fixed share of the lessons (a hash of the id), so lanes that build batches at the
// same moment can never take the same lesson
const LANES = 10
const laneOf = (id) => [...id].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7) % LANES
const free = [...new Set([...fresh, ...week, ...richest])].filter((id) => study[id] && !taken.has(id))
let order = free.filter((id) => laneOf(id) === LANE - 1)
// 2026-10-14 (the owner: "10 lanes running all the time"): a lane whose own share ran out helps the
// busy lanes, taking from the back half of their shares — an owner works from the front, so the two
// never pick the same lesson in one round; the idle lanes deal that pool out among themselves
const shares = Array.from({ length: LANES }, (_, i) => free.filter((id) => laneOf(id) === i))
const idle = shares.map((s, i) => (s.length < SIZE ? i : -1)).filter((i) => i >= 0)
if (idle.includes(LANE - 1)) {
  const pool = shares.filter((s) => s.length >= 2 * SIZE).flatMap((s) => s.slice(Math.ceil(s.length / 2)))
  const help = pool.filter((_, i) => i % idle.length === idle.indexOf(LANE - 1))
  if (help.length) console.log(`own share: ${order.length} lessons — helping the busy lanes with ${help.length}`)
  order = [...order, ...help]
}

const mine = batches.filter((b) => b.startsWith(`lane${LANE}-`)).length
const name = `lane${LANE}-${String(mine + 1).padStart(3, '0')}`
const lessons = []
const chunks = []
for (const id of order) {
  if (lessons.length >= SIZE) break
  const en = await get(`videos/transcript/${id}/en`)
  if (en?.by) continue // already translated by Claude
  const doc = await get(`videos/transcript/${id}`)
  if (!doc?.cues?.length || doc.lang !== 'he') continue
  const studyText = [
    `TÍTULO DO ESTUDO: ${doc.title}`,
    `RESUMO: ${doc.summary}`,
    `MOMENTOS: ${(doc.moments || []).map((m) => `${clock(m[0])} ${m[1]}`).join(' · ')}`,
    `FONTES CITADAS: ${(doc.sources || []).map((s) => `${clock(s[0])} ${s[2]}`).join(' · ')}`,
  ].join('\n')
  const line = (i) => `${i}|${clock(doc.cues[i][0])}|${doc.cues[i][2]}`
  const size = small.has(id) ? SMALL : CHUNK
  const parts = Math.ceil(doc.cues.length / size)
  fs.mkdirSync(path.join(DIR, name, 'in'), { recursive: true })
  for (let k = 0; k < parts; k++) {
    const a = k * size
    const b = Math.min(doc.cues.length, a + size) - 1
    const before = []
    for (let i = Math.max(0, a - BEFORE); i < a; i++) before.push(line(i))
    const body = []
    for (let i = a; i <= b; i++) body.push(line(i))
    fs.writeFileSync(
      path.join(DIR, name, 'in', `${id}.p${k}.txt`),
      [
        `videoId: ${id}`,
        `parte ${k + 1} de ${parts} · traduzir as linhas ${a} a ${b} (${b - a + 1} linhas)`,
        '',
        'ESTUDO DA AULA (contexto — já revisado, use para nomes, versículos e termos):',
        studyText,
        '',
        ...(before.length ? ['LINHAS ANTERIORES (só contexto, NÃO traduzir):', ...before, ''] : []),
        'LINHAS A TRADUZIR:',
        ...body,
      ].join('\n') + '\n',
    )
    chunks.push(`${id}.p${k}`)
  }
  lessons.push({ id, title: doc.title, lines: doc.cues.length, parts, ...(small.has(id) ? { small: 1 } : {}), from: fresh.includes(id) ? 'recente' : week.includes(id) ? 'parashá da semana' : 'mais fontes' })
  console.log(`  ${id}  ${doc.cues.length} lines → ${parts} part(s)  ${doc.title}`)
}
if (!lessons.length) {
  console.log('nothing left to translate — the library is done')
  output('batch', '')
  output('chunks', '[]')
  process.exit(0)
}
fs.mkdirSync(path.join(DIR, name, 'out'), { recursive: true })
fs.writeFileSync(path.join(DIR, name, 'out', '.keep'), '')
fs.writeFileSync(path.join(DIR, name, 'manifest.json'), JSON.stringify({ name, lane: LANE, created: new Date().toISOString(), status: 'pending', lessons, chunks }, null, 1) + '\n')
console.log(`${name}: ${lessons.length} lessons, ${chunks.length} chunks`)
output('batch', name)
output('chunks', JSON.stringify(chunks))
