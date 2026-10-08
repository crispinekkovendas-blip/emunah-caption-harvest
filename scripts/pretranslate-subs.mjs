/**
 * pretranslate-subs.mjs — translate the subtitles of every lesson with a study into English ahead
 * of time (2026-10-05: the player opens Hebrew lessons with English subtitles by default), so the
 * first viewer gets them at once instead of waiting for the translation. Same translator and same
 * cache row as the player's own request (/videos/transcript/?tl=en): Google's keyless endpoint via
 * src/utils/translate.ts, kept in global_options under videos/transcript/<id>/en.
 *
 *   node --experimental-transform-types --import ./scripts/ts-hook.mjs scripts/pretranslate-subs.mjs [--to en] [--limit N] [--minutes N]
 *
 * Runs on GitHub too (repo emunah-caption-harvest, workflow pretranslate.yml): this 8 GB machine
 * reaps long background jobs when memory runs short.
 *
 * Resumable: a video whose translation is already cached is skipped. Stops after ten failures in a
 * row (Google refusing the address) — run it again later.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SUBS_VERSION, translateCues } from '../src/utils/subs-context.ts'

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const argv = process.argv.slice(2)
const flag = (n, d) => (argv.includes(`--${n}`) ? argv[argv.indexOf(`--${n}`) + 1] : d)
const TO = flag('to', 'en')
const LIMIT = Number(flag('limit', '0')) || Infinity
// --minutes N: stop cleanly after N minutes (a GitHub job is killed at six hours)
const DEADLINE = Date.now() + (Number(flag('minutes', '0')) || Infinity) * 60000
// the cache row of one translation — the same key as KEY_TL in src/utils/transcript.ts (inlined so the
// script also runs on GitHub with only translate.ts, divine.ts and parashiot.ts beside it)
const KEY_TL = (id, tl) => `videos/transcript/${id}/${tl}`
// .env.local on this machine; the process environment on a GitHub runner (repository secrets)
const ENV_FILE = path.join(ROOT, '.env.local')
const env = !fs.existsSync(ENV_FILE)
  ? process.env
  : Object.fromEntries(
      fs
        .readFileSync(ENV_FILE, 'utf8')
        .split(/\r?\n/)
        .filter((l) => /^[A-Z_]+=/.test(l))
        .map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]),
    )
const SUPA = env.SUPABASE_URL.replace(/\/$/, '')
const H = { apikey: env.SUPABASE_SERVICE_KEY, authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}` }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function supa(url, init = {}) {
  for (let attempt = 1; ; attempt++) {
    try {
      const res = await fetch(url, {
        ...init,
        headers: { ...H, ...(init.headers || {}) },
        signal: AbortSignal.timeout(60000),
      })
      if (res.status >= 500 && attempt < 4) throw new Error(`Supabase ${res.status}`)
      return res
    } catch (err) {
      if (attempt >= 4) throw err
      await sleep(3000 * attempt)
    }
  }
}
async function get(key) {
  const res = await supa(`${SUPA}/rest/v1/global_options?select=value&key=eq.${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`Supabase ${res.status}`)
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

// the lessons with a study (the same list the library cards use), newest first
const study = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'public', 'data', 'videos', 'study.json'), 'utf8'),
).study
const ids = Object.keys(study)
// the misheard-word corrections and the Torah terms (scripts/asr-candidates.mjs + one Claude pass)
const LEXICON = JSON.parse(fs.readFileSync(path.join(ROOT, 'src', 'data', 'subs-lexicon.json'), 'utf8'))
console.log(`${ids.length} lessons with a study → subtitles in ${TO}`)
let done = 0
let skipped = 0
let failedRow = 0
let supaErrors = 0
let failed = 0
for (const id of ids) {
  if (done >= LIMIT) break
  if (Date.now() > DEADLINE) {
    console.log('time budget used — the next run carries on from here')
    break
  }
  // a slow or failing Supabase answer skips this lesson instead of ending the run (2026-10-08: three
  // runs crashed on a TimeoutError and, crashed, did not start the next); the next run retries it
  let have, doc
  try {
    have = await get(KEY_TL(id, TO))
    doc = await get(`videos/transcript/${id}`)
    supaErrors = 0
  } catch (err) {
    supaErrors++
    console.log(`      ${id}  Supabase: ${String(err?.message || err).slice(0, 80)} — skipped`)
    if (supaErrors >= 10) {
      // still a stop that chains: the next run starts after a pause and carries on from here
      console.log('time budget used — Supabase not answering, the next run carries on from here')
      break
    }
    await sleep(30000)
    continue
  }
  // kept: a translation made by Claude, or one already made with the current method (SUBS_VERSION);
  // an older line-by-line Google row is made again with whole sentences
  const current = have?.texts?.length === doc?.cues?.length && (have.by || (have.v || 1) >= SUBS_VERSION)
  if (!doc?.cues?.length || doc.lang === TO || current) {
    skipped++
    continue
  }
  const texts = doc.cues.map((c) => c[2])
  const out = await translateCues(doc.cues, doc.lang, TO, LEXICON, { delayMs: 250 })
  const ok = out.filter(Boolean).length
  if (ok >= texts.length * 0.8) {
    try {
      await put(KEY_TL(id, TO), { v: SUBS_VERSION, videoId: id, tl: TO, texts: out })
    } catch (err) {
      console.log(`      ${id}  not saved (Supabase: ${String(err?.message || err).slice(0, 80)}) — the next run redoes it`)
      await sleep(30000)
      continue
    }
    done++
    failedRow = 0
    console.log(`${String(done).padStart(4)}  ${id}  ${ok}/${texts.length} cues`)
  } else {
    failed++
    failedRow++
    console.log(`      ${id}  only ${ok}/${texts.length} translated — not saved`)
    if (failedRow >= 10) {
      console.log('ten failures in a row: Google is refusing this address — run again later')
      break
    }
    await sleep(60000)
  }
  await sleep(2000)
}
console.log(`\n${done} translated · ${skipped} already there or not needed · ${failed} failed`)
