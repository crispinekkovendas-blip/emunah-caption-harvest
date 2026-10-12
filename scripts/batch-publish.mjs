/**
 * batch-publish.mjs — check a batch's translations and put the finished lessons on the site.
 *
 *   node scripts/batch-publish.mjs batch-NNN
 *
 * A lesson whose chunks are all in out/ is checked — every line 0…n-1 exactly once, in English and
 * Portuguese, no Divine Name — and uploaded to videos/transcript/<id>/en|pt marked `by:
 * claude-sonnet-5-5` (the Google job never overwrites those). A lesson that fails has its outputs
 * removed so the next run translates it again; after 3 tries it is skipped. Writes report.md, the
 * manifest's status, and GITHUB_OUTPUT complete=true|false (true = nothing left in this batch).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const MODEL = 'claude-sonnet-5-5'
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const NAME = process.argv[2]
const DIR = path.join(ROOT, 'video-batches', NAME)
const SUPA = (process.env.SUPABASE_URL || '').replace(/\/$/, '')
const H = { apikey: process.env.SUPABASE_SERVICE_KEY, authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY}` }
const NAME_RE = new RegExp(['\\u05d9\\u05d4\\u05d5\\u05d4', '\\bYa?hweh\\b', '\\bJeh?ov[aá]h?\\b', '\\bJeov[aá]\\b', '\\bY-?H-?[WV]-?H\\b'].join('|'), 'i')
const output = (k, v) => {
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `${k}=${v}\n`)
  console.log(`${k}=${v}`)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function supa(url, init = {}) {
  for (let a = 1; ; a++) {
    try {
      const res = await fetch(url, { ...init, headers: { ...H, ...(init.headers || {}) }, signal: AbortSignal.timeout(60000) })
      if (res.status >= 500 && a < 4) throw new Error(`Supabase ${res.status}`)
      return res
    } catch (err) {
      if (a >= 4) throw err
      await sleep(5000 * a)
    }
  }
}
async function get(key) {
  const res = await supa(`${SUPA}/rest/v1/global_options?select=value&key=eq.${encodeURIComponent(key)}`)
  const row = (await res.json())[0]
  return row ? (typeof row.value === 'string' ? JSON.parse(row.value) : row.value) : null
}
async function put(key, value) {
  const res = await supa(`${SUPA}/rest/v1/global_options?on_conflict=key`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', prefer: 'resolution=merge-duplicates,return=minimal' },
    body: JSON.stringify([{ key, value: JSON.stringify(value), updated_at: new Date().toISOString() }]),
  })
  if (!res.ok) throw new Error(`Supabase ${res.status} ${await res.text()}`)
}

const manifest = JSON.parse(fs.readFileSync(path.join(DIR, 'manifest.json'), 'utf8'))
manifest.tries ||= {}
manifest.done ||= []
manifest.skipped ||= []
const rows = []
for (const lesson of manifest.lessons) {
  const { id, parts } = lesson
  if (manifest.done.includes(id) || manifest.skipped.includes(id)) continue
  const files = Array.from({ length: parts }, (_, k) => path.join(DIR, 'out', `${id}.p${k}.txt`))
  if (!files.every((f) => fs.existsSync(f))) {
    rows.push(`| ${id} | waiting | ${files.filter((f) => fs.existsSync(f)).length}/${parts} parts |`)
    continue
  }
  try {
    const doc = await get(`videos/transcript/${id}`)
    const n = doc.cues.length
    const en = new Array(n).fill(null)
    const pt = new Array(n).fill(null)
    for (const f of files) {
      for (const raw of fs.readFileSync(f, 'utf8').replace(/\r\n/g, '\n').split('\n')) {
        if (!raw.trim()) continue
        const c = raw.split('\t')
        const i = Number(c[0])
        if (c.length !== 3 || !Number.isInteger(i) || i < 0 || i >= n) throw new Error(`bad line "${raw.slice(0, 50)}"`)
        if (en[i] != null) throw new Error(`line ${i} twice`)
        en[i] = c[1].trim()
        pt[i] = c[2].trim()
      }
    }
    const missing = en.filter((t, i) => t == null || pt[i] == null).length
    if (missing) throw new Error(`${missing} lines missing`)
    if (NAME_RE.test(en.join('\n') + pt.join('\n'))) throw new Error('the Divine Name is written out')
    await put(`videos/transcript/${id}/en`, { v: 2, videoId: id, tl: 'en', texts: en, by: MODEL })
    await put(`videos/transcript/${id}/pt`, { v: 2, videoId: id, tl: 'pt', texts: pt, by: MODEL })
    manifest.done.push(id)
    rows.push(`| ${id} | ✓ published | ${n} lines · ${lesson.title} |`)
  } catch (err) {
    manifest.tries[id] = (manifest.tries[id] || 0) + 1
    for (const f of files) fs.rmSync(f, { force: true })
    if (manifest.tries[id] >= 3) {
      manifest.skipped.push(id)
      rows.push(`| ${id} | skipped after 3 tries | ${err.message} |`)
    } else rows.push(`| ${id} | ✗ will be redone (try ${manifest.tries[id]}) | ${err.message} |`)
  }
}
const finished = manifest.lessons.every((l) => manifest.done.includes(l.id) || manifest.skipped.includes(l.id))
manifest.status = finished ? 'done' : 'pending'
fs.writeFileSync(path.join(DIR, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n')

// tokens, from the agents' usage files
let inTok = 0
let outTok = 0
let cost = 0
let runs = 0
let refused = 0
for (const f of fs.readdirSync(path.join(DIR, 'out')).filter((x) => x.endsWith('.usage.json'))) {
  try {
    const u = JSON.parse(fs.readFileSync(path.join(DIR, 'out', f), 'utf8'))
    // modelUsage is cumulative over the agent's turns; the top-level usage is the last turn only
    const models = Object.values(u.modelUsage || {})
    if (!models.length) {
      refused++
      continue
    }
    runs++
    for (const m of models) {
      inTok += (m.inputTokens || 0) + (m.cacheReadInputTokens || 0) + (m.cacheCreationInputTokens || 0)
      outTok += m.outputTokens || 0
      cost += m.costUSD || 0
    }
  } catch {}
}
const report = [
  `# ${NAME}`,
  '',
  `${manifest.done.length} of ${manifest.lessons.length} lessons published · ${manifest.skipped.length} skipped · status **${manifest.status}**`,
  `Tokens (${runs} agent runs with a record${refused ? `, ${refused} refused or without record` : ''}): ${(inTok / 1e6).toFixed(1)}M in (mostly cache) · ${(outTok / 1e6).toFixed(2)}M out${cost ? ` · API-equivalent ${cost.toFixed(2)}` : ''}`,
  '',
  '| lesson | state | detail |',
  '|---|---|---|',
  ...manifest.lessons.map((l) =>
    manifest.done.includes(l.id) ? `| ${l.id} | ✓ published | ${l.lines} lines · ${l.title} |` : rows.find((r) => r.startsWith(`| ${l.id} `)) || `| ${l.id} | skipped | |`,
  ),
  '',
].join('\n')
fs.writeFileSync(path.join(DIR, 'report.md'), report)
console.log(report)
output('complete', finished ? 'true' : 'false')
