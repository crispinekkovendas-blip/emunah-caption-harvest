/**
 * subs-context.ts — subtitle translation that reads whole sentences (2026-10-07).
 *
 * Google translated each subtitle line on its own, and a line is usually half a sentence of
 * YouTube's automatic Hebrew — misheard words included. Three fixes, all without AI per line:
 *
 *  1. the misheard words are corrected first, from a list made once for the whole library
 *     (scripts/asr-candidates.mjs + one Claude pass → src/data/subs-lexicon.json, `fix`);
 *  2. Torah terms, sages, books, festivals and the parashiot are masked and come back exactly as
 *     the site writes them in each language (`terms`, plus the parashiot table);
 *  3. consecutive lines are joined into sentences (cut at pauses and at ~200 characters),
 *     translated whole, and the translation is spread back over the lines by their length — the
 *     timing of each subtitle stays where it was.
 *
 * The Divine Name stays masked by translateBatch itself (divine.ts). Used by the site's on-demand
 * translation (/videos/transcript/?tl=) and by scripts/pretranslate-subs.mjs on GitHub.
 */
import { parashiot } from '../data/parashiot.ts'
import { translateBatch } from './translate'

export type SubCue = [number, number, string]
/** fix: misheard word → what was said; terms: word or phrase → [English, Portuguese] */
export interface SubsLexicon {
  fix: Record<string, string>
  terms: Record<string, [string, string]>
}
/** bumped when the method changes: rows below it are translated again */
export const SUBS_VERSION = 2

const bare = (s: string) => s.normalize('NFD').replace(/[֑-ׇ]/g, '')
const PREFIXES = ['ו', 'ה', 'ב', 'ל', 'מ', 'ש', 'כ']

/** the parashiot as terms: "פרשת בראשית" → Parashat Bereshit / Parashá Bereshit */
const PARASHA_TERMS: Record<string, [string, string]> = Object.fromEntries(
  parashiot.flatMap((p) => {
    const he = bare(p.hebrewName).replace(/[^א-ת ]/g, '').trim()
    const en = (p.hebcalNames && p.hebcalNames[0]) || p.name
    return he ? [[`פרשת ${he}`, [`Parashat ${en}`, `Parashat ${p.name}`] as [string, string]]] : []
  }),
)

/** a misheard word, with up to two prefix letters peeled off, corrected from the list */
function fixWord(w: string, fix: Record<string, string>): string {
  if (fix[w]) return fix[w]
  for (const a of PREFIXES) {
    if (!w.startsWith(a)) continue
    const r = w.slice(1)
    if (fix[r]) return a + fix[r]
    for (const b of PREFIXES) if (r.startsWith(b) && fix[r.slice(1)]) return a + b + fix[r.slice(1)]
  }
  return w
}
export function correctHebrew(text: string, fix: Record<string, string>): string {
  if (!fix || !Object.keys(fix).length) return text
  return text
    .split(/(\s+)/)
    .map((tok) => {
      const m = tok.match(/^([^א-ת]*)([א-ת"'׳״]+)([^א-ת]*)$/)
      return m ? m[1] + fixWord(m[2], fix) + m[3] : tok
    })
    .join('')
}

/**
 * Masks the terms with placeholders Google leaves alone (Xq51, Xq52…: the probed Xq prefix, numbered
 * past the range divine.ts uses — translateBatch then picks another prefix for the Name itself).
 */
function maskTerms(text: string, terms: Record<string, [string, string]>, phrases: string[], lang: 0 | 1): { text: string; slots: string[] } {
  const slots: string[] = []
  const put = (out: string) => {
    if (slots.length >= 40) return null
    slots.push(out)
    return ` Xq${50 + slots.length} `
  }
  let s = text
  // phrases first (several words), whole words only — Hebrew has no \b, so look at the letters around
  for (const ph of phrases) {
    if (!s.includes(ph)) continue
    s = s.replace(new RegExp(`(?<![א-ת])${ph.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![א-ת])`, 'g'), (m) => put(terms[ph][lang]) ?? m)
  }
  s = s
    .split(/(\s+)/)
    .map((tok) => {
      const m = tok.match(/^([^א-ת]*)([א-ת"'׳״]+)([^א-ת]*)$/)
      if (!m || !terms[m[2]]) return tok
      const p = put(terms[m[2]][lang])
      return p ? m[1] + p + m[3] : tok
    })
    .join('')
  return { text: s.replace(/\s{2,}/g, ' ').trim(), slots }
}
function unmaskTerms(text: string, slots: string[]): string {
  if (!slots.length) return text
  return text.replace(/Xq\s?(\d{2})/gi, (whole, n) => {
    const i = Number(n) - 51
    return i >= 0 && i < slots.length ? slots[i] : whole
  })
}

/** consecutive cues → sentence windows: cut at a pause, at the end of a sentence, or at ~200 characters */
function windows(cues: SubCue[], maxChars = 200): number[][] {
  const out: number[][] = []
  let cur: number[] = []
  let len = 0
  cues.forEach((c, i) => {
    cur.push(i)
    len += c[2].length + 1
    const next = cues[i + 1]
    const pause = next ? next[0] - c[1] : 99
    if (!next || len >= maxChars || (len >= 40 && (pause >= 0.8 || /[.?!]$/.test(c[2].trim())))) {
      out.push(cur)
      cur = []
      len = 0
    }
  })
  return out
}

/** a window's translation spread back over its lines, in proportion to their length */
function spread(translation: string, sizes: number[]): string[] {
  if (sizes.length === 1) return [translation]
  const words = translation.split(/\s+/).filter(Boolean)
  const total = sizes.reduce((a, b) => a + b, 0) || 1
  const out: string[] = []
  let used = 0
  let cum = 0
  sizes.forEach((sz, k) => {
    cum += sz
    let end = k === sizes.length - 1 ? words.length : Math.round((words.length * cum) / total)
    // every line keeps at least one word while words remain for the lines after it
    const left = sizes.length - k - 1
    end = Math.max(end, Math.min(used + 1, words.length - left))
    end = Math.min(end, words.length - left)
    out.push(words.slice(used, Math.max(used, end)).join(' '))
    used = Math.max(used, end)
  })
  return out
}

/** One translation per cue (null where a batch failed), read as whole sentences. */
export async function translateCues(
  cues: SubCue[],
  sl: string,
  tl: string,
  lexicon: SubsLexicon | null,
  opts: { delayMs?: number; onProgress?: (done: number, total: number) => void | Promise<void> } = {},
): Promise<(string | null)[]> {
  const fix = sl === 'he' ? lexicon?.fix || {} : {}
  const terms = sl === 'he' ? { ...PARASHA_TERMS, ...(lexicon?.terms || {}) } : {}
  const phrases = Object.keys(terms)
    .filter((k) => k.includes(' '))
    .sort((a, b) => b.length - a.length)
  const lang: 0 | 1 = tl === 'pt' ? 1 : 0
  const fixed = cues.map((c) => correctHebrew(c[2], fix))
  const groups = windows(cues.map((c, i) => [c[0], c[1], fixed[i]] as SubCue))
  const masked = groups.map((g) => maskTerms(g.map((i) => fixed[i]).join(' '), terms, phrases, lang))
  const got = await translateBatch(
    masked.map((m) => m.text),
    sl,
    tl,
    { delayMs: opts.delayMs ?? 200, maxChars: 5000, onProgress: opts.onProgress ? (d, n) => opts.onProgress!(d, n) : undefined },
  )
  const out: (string | null)[] = new Array(cues.length).fill(null)
  groups.forEach((g, k) => {
    const t = got[k]
    if (!t) return
    const parts = spread(unmaskTerms(t, masked[k].slots), g.map((i) => Math.max(1, fixed[i].length)))
    g.forEach((i, j) => (out[i] = parts[j] || '…'))
  })
  return out
}
