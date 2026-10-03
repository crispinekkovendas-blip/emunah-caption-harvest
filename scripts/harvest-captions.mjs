/**
 * harvest-captions.mjs — take YouTube's own captions for the library's videos and put them in the
 * site's transcript cache, so the AI only has to write the summary.
 *
 * Why this exists: a video read by Gemini costs up to nine requests (eight clips + the summary).
 * A video whose words come from YouTube costs one — the summary — because the cues are already
 * there. On the free tier that is the difference between two videos a day and twenty.
 *
 * Why it runs here and not on the site: YouTube's timedtext endpoint answers 200 with zero bytes to
 * anything that cannot prove it is a browser (re-probed 2026-09-27, from this machine as much as
 * from the edge). yt-dlp gets them by asking as the android-vr client — but it needs Python and a
 * home connection, neither of which Vercel has. So this is a hand-run harvest, not a cron.
 *
 * It is deliberately slow and resumable. YouTube rate-limits captions hard (HTTP 429 after a few);
 * the script waits between videos, backs off when refused, remembers what it finished in
 * scripts/.harvest-state.json, and stops itself when the refusals say the day's budget is gone.
 *
 * Usage
 *   node scripts/harvest-captions.mjs --lang pt --limit 20          harvest 20 from the pt shelf
 *   node scripts/harvest-captions.mjs --lang he --gap 30            wait 30 s between videos
 *   node scripts/harvest-captions.mjs --ids abc123XYZ_1,def456…     just these
 *   node scripts/harvest-captions.mjs --lang pt --dry-run           say what it would do
 *   node scripts/harvest-captions.mjs --lang pt --force             re-fetch ones already cached
 *
 * What lands in Supabase is a transcript document with cues and no summary, which is exactly what
 * the site's "Gerar resumo" button completes in a single AI request.
 */
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(HERE, '..')
const STATE_FILE = path.join(HERE, '.harvest-state.json')
const TMP = path.join(os.tmpdir(), 'emunah-captions')

/* ── arguments ─────────────────────────────────────────────────────────── */
const argv = process.argv.slice(2)
const flag = (name, fallback = '') => {
  const i = argv.indexOf(`--${name}`)
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : fallback
}
const has = (name) => argv.includes(`--${name}`)
const LANG = flag('lang', 'pt')
const LIMIT = Number(flag('limit', '0')) || Infinity
const GAP = Number(flag('gap', '20')) * 1000
const IDS = flag('ids', '')
  .split(',')
  .map((s) => s.trim())
  .filter((s) => /^[\w-]{11}$/.test(s))
const DRY = has('dry-run')
const FORCE = has('force')
/**
 * When YouTube cuts the address off the budget returns after a while, so the script rests instead
 * of giving up: six half-hour rests is an evening of patience. --rests 0 stops at the first wall.
 */
const RESTS = Number(flag('rests', '6'))
const REST_MS = Number(flag('rest-minutes', '30')) * 60000

/** which caption track to ask for, per shelf: one language, because every extra track is another
 * request against the same limit. The fallback widens only when YouTube says the first is absent. */
const TRACKS = {
  own: ['pt', 'pt.*'],
  pt: ['pt', 'pt.*'],
  es: ['es', 'es.*'],
  he: ['iw', 'iw.*,he.*'],
  tefilot: ['iw', 'iw.*,he.*'],
  rezas: ['iw', 'iw.*,he.*'],
  dedicados: ['iw', 'iw.*,he.*'],
}
/** the language code the document carries, as the site's LANG_NAMES knows it */
const DOC_LANG = { own: 'pt', pt: 'pt', es: 'es', he: 'he', tefilot: 'he', rezas: 'he', dedicados: 'he' }

/* ── environment ───────────────────────────────────────────────────────── */
// .env.local on this machine; the process environment on a GitHub runner (repository secrets)
const ENV_FILE = path.join(ROOT, '.env.local')
const env = fs.existsSync(ENV_FILE)
  ? Object.fromEntries(
      fs
        .readFileSync(ENV_FILE, 'utf8')
        .split(/\r?\n/)
        .filter((l) => /^[A-Z_]+=/.test(l))
        .map((l) => {
          const i = l.indexOf('=')
          return [l.slice(0, i), l.slice(i + 1)]
        }),
    )
  : process.env
const PYTHON = process.env.PYTHON || 'python'
const SUPA = env.SUPABASE_URL?.replace(/\/$/, '')
const SERVICE = env.SUPABASE_SERVICE_KEY
const ANON = env.SUPABASE_ANON_KEY || SERVICE
if (!SUPA || !SERVICE) {
  console.error('no SUPABASE_URL / SUPABASE_SERVICE_KEY in .env.local — nothing to write to')
  process.exit(1)
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const KEY = (id) => `videos/transcript/${id}`

/* ── state ─────────────────────────────────────────────────────────────── */
const state = fs.existsSync(STATE_FILE) ? JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) : { done: [], failed: {}, runs: [] }
const saveState = () => fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 1))
const done = new Set(state.done)

/* ── what the cache already holds ──────────────────────────────────────── */
async function cachedIds() {
  const q = new URLSearchParams({ select: 'key,value', key: 'like.videos/transcript/*', limit: '5000' })
  const res = await fetch(`${SUPA}/rest/v1/global_options?${q}`, { headers: { apikey: ANON, authorization: `Bearer ${ANON}` } })
  if (!res.ok) throw new Error(`Supabase ${res.status}`)
  const rows = await res.json()
  const withCues = new Set()
  const withSummary = new Set()
  for (const r of rows) {
    const id = r.key.slice('videos/transcript/'.length)
    if (!/^[\w-]{11}$/.test(id)) continue
    let j
    try {
      j = JSON.parse(r.value)
    } catch {
      continue
    }
    if (j.unavailable) continue
    if (Array.isArray(j.cues) && j.cues.length) withCues.add(id)
    if (String(j.summary || '').trim()) withSummary.add(id)
  }
  return { withCues, withSummary }
}

/* ── json3 → the site's cues ───────────────────────────────────────────── */
/**
 * YouTube's automatic captions arrive as a rolling window: a line of words, then an `aAppend`
 * event carrying only a newline, then the next line. The append events are punctuation for the
 * window, not speech, so they go. Short lines are then merged into cues of a few seconds, which is
 * what the player's subtitle layer and the prayer sync expect.
 */
export function cuesFromJson3(json, maxSeconds = 6, maxChars = 90) {
  const lines = []
  for (const e of json.events || []) {
    if (!e.segs || e.aAppend) continue
    const text = e.segs
      .map((s) => s.utf8 || '')
      .join('')
      .replace(/\s+/g, ' ')
      .trim()
    if (!text) continue
    const start = (e.tStartMs || 0) / 1000
    const end = start + (e.dDurationMs || 0) / 1000
    lines.push([start, end, text])
  }
  lines.sort((a, b) => a[0] - b[0])
  const out = []
  for (const [s, e, t] of lines) {
    const prev = out[out.length - 1]
    const joined = prev ? `${prev[2]} ${t}` : t
    const fits = prev && e - prev[0] <= maxSeconds && joined.length <= maxChars && !/[.!?…]$/.test(prev[2])
    if (fits) {
      prev[1] = Math.max(prev[1], e)
      prev[2] = joined
    } else out.push([s, Math.max(e, s + 0.4), t])
  }
  // no overlaps at all: an end never reaches the next start, and a start never walks backwards.
  // (YouTube's rolling windows do overlap; findCue in the player assumes they do not.)
  const clean = []
  for (const c of out) {
    const prev = clean[clean.length - 1]
    let [s, e, t] = c
    if (prev) {
      if (s < prev[1]) prev[1] = Math.max(prev[0] + 0.05, Math.min(prev[1], s))
      if (s < prev[1]) s = prev[1]
      if (e <= s) e = s + 0.05
    }
    clean.push([Math.round(s * 100) / 100, Math.round(e * 100) / 100, t])
  }
  return clean
}

/* ── yt-dlp ────────────────────────────────────────────────────────────── */
function ytdlp(videoId, subLangs) {
  fs.mkdirSync(TMP, { recursive: true })
  for (const f of fs.readdirSync(TMP)) if (f.startsWith(videoId)) fs.rmSync(path.join(TMP, f), { force: true })
  const r = spawnSync(
    PYTHON,
    [
      '-m',
      'yt_dlp',
      '--skip-download',
      '--write-auto-subs',
      '--write-subs',
      '--sub-langs',
      subLangs,
      '--sub-format',
      'json3',
      '--no-warnings',
      '--quiet',
      '--no-playlist',
      '--retries',
      '2',
      '--extractor-retries',
      '2',
      '-o',
      path.join(TMP, '%(id)s.%(ext)s'),
      `https://www.youtube.com/watch?v=${videoId}`,
    ],
    { encoding: 'utf8', timeout: 180000 },
  )
  const files = fs
    .readdirSync(TMP)
    .filter((f) => f.startsWith(videoId) && f.endsWith('.json3'))
    .map((f) => path.join(TMP, f))
  const err = `${r.stderr || ''}`.trim()
  return { files, err, rateLimited: /429|Too Many Requests/i.test(err), absent: /no subtitles|There are no subtitles/i.test(err) }
}

/* ── Supabase ──────────────────────────────────────────────────────────── */
async function put(id, doc) {
  const res = await fetch(`${SUPA}/rest/v1/global_options?on_conflict=key`, {
    method: 'POST',
    headers: { apikey: SERVICE, authorization: `Bearer ${SERVICE}`, 'content-type': 'application/json', prefer: 'resolution=merge-duplicates,return=minimal' },
    body: JSON.stringify([{ key: KEY(id), value: JSON.stringify(doc), updated_at: new Date().toISOString() }]),
  })
  await res.text().catch(() => '')
  return res.ok
}

/* ── the walk ──────────────────────────────────────────────────────────── */
async function main() {
  const seedPath = path.join(ROOT, 'public', 'data', 'videos', `${LANG}.json`)
  if (!IDS.length && !fs.existsSync(seedPath)) {
    console.error(`no seed for shelf "${LANG}" (${seedPath})`)
    process.exit(1)
  }
  const seed = fs.existsSync(seedPath) ? JSON.parse(fs.readFileSync(seedPath, 'utf8')) : { videos: [] }
  const { withCues, withSummary } = await cachedIds()

  let pool = IDS.length ? IDS.map((id) => seed.videos.find((v) => v.videoId === id) || { videoId: id, title: id, duration: 0 }) : seed.videos
  pool = pool.filter((v) => v.videoId && (FORCE || (!withCues.has(v.videoId) && !done.has(v.videoId))))
  const todo = pool.slice(0, LIMIT === Infinity ? pool.length : LIMIT)

  console.log(`shelf ${LANG} · ${seed.videos.length} videos · ${withCues.size} already have cues (${withSummary.size} of them a summary)`)
  console.log(`${pool.length} left to harvest, taking ${todo.length} this run · ${GAP / 1000}s between videos\n`)
  if (DRY) {
    for (const v of todo.slice(0, 20)) console.log('  would harvest', v.videoId, `${Math.round((v.duration || 0) / 60)}min`, String(v.title || '').slice(0, 60))
    if (todo.length > 20) console.log(`  …and ${todo.length - 20} more`)
    return
  }

  const [primary, wider] = TRACKS[LANG] || TRACKS.pt
  let ok = 0
  let refused = 0
  let missing = 0
  let streak = 0
  let walled = false
  const gap = GAP
  for (const [i, v] of todo.entries()) {
    const id = v.videoId
    let attempt = 0
    let got = null
    let why = ''
    while (attempt < 3 && !got) {
      const langs = attempt === 0 ? primary : wider
      const r = ytdlp(id, langs)
      if (r.files.length) {
        // prefer the track whose name matches the shelf language, else the biggest file
        const best = r.files.sort((a, b) => fs.statSync(b).size - fs.statSync(a).size).find((f) => new RegExp(`\\.(${primary}|${DOC_LANG[LANG]})[-.]`).test(path.basename(f))) || r.files[0]
        got = JSON.parse(fs.readFileSync(best, 'utf8'))
        why = path.basename(best).replace(`${id}.`, '').replace('.json3', '')
        for (const f of r.files) fs.rmSync(f, { force: true })
        break
      }
      if (r.absent && attempt === 0) {
        attempt++ // try the wider match once
        continue
      }
      if (r.rateLimited) {
        const wait = Math.min(180000, gap * Math.pow(2, attempt + 1))
        process.stdout.write(`  ${id} refused (429) — waiting ${Math.round(wait / 1000)}s\n`)
        await sleep(wait)
        attempt++
        continue
      }
      why = r.err.split('\n').pop()?.slice(0, 100) || 'no subtitles'
      break
    }

    if (!got) {
      const rate = /429/.test(why) || attempt >= 3
      if (rate) refused++
      else missing++
      streak++
      state.failed[id] = why || 'rate limited'
      console.log(`  ${String(i + 1).padStart(3)}/${todo.length} ${id}  —  no captions  (${(why || 'rate limited').slice(0, 60)})`)
      if (streak >= 6) {
        walled = true
        console.log('\nsix in a row refused: YouTube has cut this address off for now.')
        break
      }
      await sleep(gap)
      continue
    }

    const cues = cuesFromJson3(got)
    const duration = v.duration || (cues.length ? cues[cues.length - 1][1] : 0)
    // a handful of cues for an hour of video means the track is a stub, not a transcript
    if (cues.length < 5 || (duration > 300 && cues.length < duration / 120)) {
      missing++
      streak = 0
      state.failed[id] = `thin track: ${cues.length} cues for ${Math.round(duration)}s`
      console.log(`  ${String(i + 1).padStart(3)}/${todo.length} ${id}  —  track too thin (${cues.length} cues)`)
      await sleep(gap)
      continue
    }
    const doc = {
      v: 1,
      videoId: id,
      lang: DOC_LANG[LANG] || 'pt',
      duration: Math.round(duration),
      cues,
      title: '',
      summary: '',
      moments: [],
      model: 'youtube-asr',
      source: `youtube:${why}`,
      generated: new Date().toISOString(),
    }
    const wrote = await put(id, doc)
    if (wrote) {
      ok++
      streak = 0
      done.add(id)
      state.done = [...done]
      delete state.failed[id]
      saveState()
      const words = cues.reduce((n, c) => n + c[2].split(' ').length, 0)
      console.log(`  ${String(i + 1).padStart(3)}/${todo.length} ${id}  ✓  ${cues.length} cues · ${words} words · ${Math.round(duration / 60)}min · track ${why}`)
    } else {
      console.log(`  ${String(i + 1).padStart(3)}/${todo.length} ${id}  —  Supabase refused the write`)
      state.failed[id] = 'supabase write failed'
    }
    if (i < todo.length - 1) await sleep(gap)
  }

  state.runs = [...(state.runs || []).slice(-9), { at: new Date().toISOString(), lang: LANG, ok, refused, missing }]
  saveState()
  console.log(`\n${ok} harvested · ${refused} refused by YouTube · ${missing} without usable captions`)
  if (ok) {
    console.log(`Those ${ok} now show subtitles at once and need ONE AI request each for the summary —`)
    console.log(`open them on the site and press "Gerar resumo", or use the row button.`)
  }
  if (refused) console.log('Refusals are the caption rate limit, not a bug — the address needs to cool off.')
  return { ok, refused, missing, walled, left: pool.length - ok }
}

/**
 * Run, and when YouTube shuts the door, wait for it to open again: a shelf is an evening's work
 * with rests in it, not one sitting. --rests 0 stops at the first wall.
 */
async function harvest() {
  for (let rest = 0; ; rest++) {
    const r = await main()
    if (DRY || !r || !r.walled || r.left <= 0) return
    if (rest >= RESTS) {
      console.log(`
Stopping after ${RESTS} rests. Run it again later — it resumes where it stopped.`)
      return
    }
    console.log(`
Resting ${REST_MS / 60000} min (rest ${rest + 1} of ${RESTS}); back at ${new Date(Date.now() + REST_MS).toLocaleTimeString()}. ${r.left} videos still to go.
`)
    await sleep(REST_MS)
  }
}

// only when run, never when imported: a test that wants cuesFromJson3 must not start a harvest
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  harvest().catch((e) => {
    console.error(e)
    process.exit(1)
  })
}
