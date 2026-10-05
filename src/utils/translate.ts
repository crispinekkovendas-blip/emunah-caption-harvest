/**
 * translate.ts — keyless Hebrew → English machine translation for video titles.
 *
 * Provider: Google's dictionary-extension endpoint (clients5.google.com, batched, no key), with
 * MyMemory as a one-by-one fallback. Titles are pre-processed so the parts MT gets wrong stay
 * right: Hebrew year abbreviations (תשפ"ו → 5786) and parashá names (פרשת האזינו → Parashat
 * Ha'azinu, from the site's own table). Works in Node (seed script) and on the Vercel edge (feed).
 */
import { parashiot } from '../data/parashiot.ts'

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'
const GEMATRIA: Record<string, number> = {
  א: 1, ב: 2, ג: 3, ד: 4, ה: 5, ו: 6, ז: 7, ח: 8, ט: 9, י: 10, כ: 20, ך: 20, ל: 30, מ: 40, ם: 40, נ: 50, ן: 50, ס: 60, ע: 70, פ: 80, ף: 80, צ: 90, ץ: 90, ק: 100, ר: 200, ש: 300, ת: 400,
}

const stripNikud = (s: string) => s.normalize('NFD').replace(/[֑-ׇ]/g, '')

/** "תשפ"ו", "התשפ״ו", "ה'תשפ"ו" → 5786 */
export function hebrewYearToNumber(token: string): number | null {
  const letters = token.replace(/[^א-ת]/g, '')
  if (letters.length < 3 || letters.length > 6) return null
  let body = letters
  let base = 0
  if (body.startsWith('ה') && body.length >= 4) {
    body = body.slice(1)
    base = 5000
  }
  if (!body.startsWith('ת')) return null
  let n = 0
  for (const ch of body) n += GEMATRIA[ch] || 0
  if (!base) base = 5000
  const year = base + n
  return year >= 5700 && year <= 5900 ? year : null
}

/** English spelling (hebcal) rather than the site's Portuguese one: Bo, Vayikra, Ha'Azinu… */
const PARASHA_HE: { he: string; name: string }[] = parashiot
  .map((p) => ({ he: stripNikud(p.hebrewName).replace(/[^א-ת\s]/g, '').trim(), name: (p.hebcalNames && p.hebcalNames[0]) || p.name }))
  .filter((p) => p.he.length >= 2)
  .sort((a, b) => b.he.length - a.he.length)

/** Replace what MT mangles: Hebrew years and parashá names (prefixed by פרשת/פרשה or bare). */
export function preprocessHebrewTitle(title: string): string {
  let t = title
  // years: תשפ"ו, התשפ״ו, ה'תשפ"ו — with any quote-like mark before the last letter
  t = t.replace(/(?<![א-ת])(?:ה['׳]?)?ת[א-ת]{1,3}["״'׳′]?[א-ת](?![א-ת])/g, (m) => {
    const y = hebrewYearToNumber(m)
    return y ? String(y) : m
  })
  for (const p of PARASHA_HE) {
    const re = new RegExp(`(פרש(?:ת|ה|יות)\\s+)?(?<![\\u05d0-\\u05ea])(?:ו|ב|ל|ה)?${p.he.replace(/\s+/g, '\\s+')}(?![\\u05d0-\\u05ea])`, 'g')
    t = t.replace(re, (_m, pre) => (pre ? `Parashat ${p.name}` : p.name))
  }
  return t
}

import { maskDivine, unmaskDivine } from './divine'

/** Google's language codes differ from the site's for a few languages */
const GOOGLE_CODE: Record<string, string> = { he: 'iw', 'zh-Hans': 'zh-CN', 'zh-Hant': 'zh-TW', tl: 'fil', no: 'no' }
const googleCode = (c: string) => GOOGLE_CODE[c] || c

async function googleBatch(texts: string[], sl = 'iw', tl = 'en'): Promise<(string | null)[] | null> {
  const url = `https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=${googleCode(sl)}&tl=${googleCode(tl)}&${texts.map((q) => `q=${encodeURIComponent(q)}`).join('&')}`
  const res = await fetch(url, { headers: { 'user-agent': UA }, signal: AbortSignal.timeout(8000) })
  if (!res.ok) return null
  const j = (await res.json()) as unknown
  if (!Array.isArray(j)) return null
  // one string per text; single-text responses can be nested one level deeper
  const flat = j.map((x) => (Array.isArray(x) ? x[0] : x))
  if (flat.length !== texts.length) return null
  return flat.map((x) => (typeof x === 'string' && x.trim() ? x.trim() : null))
}

async function myMemory(text: string): Promise<string | null> {
  const res = await fetch(`https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=he|en`, { headers: { 'user-agent': UA }, signal: AbortSignal.timeout(8000) })
  if (!res.ok) return null
  const j = (await res.json()) as { responseData?: { translatedText?: string } }
  const t = j.responseData?.translatedText
  return t && !/QUERY LENGTH LIMIT|MYMEMORY WARNING/i.test(t) ? t : null
}

/** Clean up MT leftovers: doubled spaces, stray quotes around years. */
function tidy(s: string): string {
  return s.replace(/\s+/g, ' ').replace(/\s+([,.!?|])/g, '$1').trim()
}

export interface TranslateOptions {
  batchSize?: number
  delayMs?: number
  /** stop translating after this many ms (edge budget); remaining items come back null */
  budgetMs?: number
  fallback?: boolean
}

/**
 * Generic batch translation (subtitle cues): any Google pair, no Hebrew pre-processing, batches
 * sized by URL length. Returns one entry per input (null when a batch failed twice).
 */
export async function translateBatch(
  texts: string[],
  sl: string,
  tl: string,
  opts: { delayMs?: number; maxChars?: number; onProgress?: (done: number, total: number) => void | Promise<void> } = {},
): Promise<(string | null)[]> {
  const { delayMs = 150, maxChars = 5500, onProgress } = opts
  const out: (string | null)[] = new Array(texts.length).fill(null)
  // the Divine Name is never translated: mask it, translate, put it back (see divine.ts)
  const masked = maskDivine(texts)
  const src = masked.texts
  let i = 0
  while (i < src.length) {
    // fill a batch up to the URL budget (percent-encoded length)
    let j = i
    let size = 0
    while (j < src.length && j - i < 25) {
      const enc = encodeURIComponent(src[j]).length + 3
      if (size && size + enc > maxChars) break
      size += enc
      j++
    }
    const slice = src.slice(i, j)
    let got: (string | null)[] | null = null
    for (let attempt = 0; attempt < 2 && !got; attempt++) {
      if (attempt) await new Promise((r) => setTimeout(r, 1500))
      try {
        got = await googleBatch(slice, sl, tl)
      } catch {
        got = null
      }
    }
    if (got) for (let k = 0; k < slice.length; k++) out[i + k] = got[k] ? unmaskDivine(tidy(got[k] as string), masked.slots[i + k], masked.prefix) : null
    i = j
    if (onProgress) await onProgress(i, texts.length)
    if (i < src.length && delayMs) await new Promise((r) => setTimeout(r, delayMs))
  }
  return out
}

/** Translate Hebrew titles to English. Returns one entry per input (null when unavailable). */
export async function translateTitlesHeEn(titles: string[], opts: TranslateOptions = {}): Promise<(string | null)[]> {
  const { batchSize = 20, delayMs = 250, budgetMs = 0, fallback = true } = opts
  const out: (string | null)[] = new Array(titles.length).fill(null)
  const started = Date.now()
  for (let i = 0; i < titles.length; i += batchSize) {
    if (budgetMs && Date.now() - started > budgetMs) break
    const slice = titles.slice(i, i + batchSize)
    const masked = maskDivine(slice.map(preprocessHebrewTitle))
    const prepared = masked.texts
    let got: (string | null)[] | null = null
    try {
      got = await googleBatch(prepared)
    } catch {
      got = null
    }
    if (!got && fallback) {
      got = []
      for (const p of prepared) {
        if (budgetMs && Date.now() - started > budgetMs) {
          got.push(null)
          continue
        }
        try {
          got.push(await myMemory(p))
        } catch {
          got.push(null)
        }
      }
    }
    if (got) for (let k = 0; k < slice.length; k++) out[i + k] = got[k] ? unmaskDivine(tidy(got[k] as string), masked.slots[k], masked.prefix) : null
    if (delayMs && i + batchSize < titles.length) await new Promise((r) => setTimeout(r, delayMs))
  }
  return out
}
