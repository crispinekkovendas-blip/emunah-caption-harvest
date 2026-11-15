/**
 * reply-lines.mjs — read the lines of one Claude translation reply (2026-11-15), for scripts/batch-reply.mjs (a new
 * reply) and scripts/batch-salvage.mjs (the saved ones), so both read a reply the same way.
 *
 *   readReply(text, from, to) → { good: Map<n, [english, portuguese]>, en: Map<n, english> }
 *
 * The asked format is N<TAB>English<TAB>Portuguese. What came back instead, measured on 42,835 saved replies:
 *   - a stray tab, or a line split in two (N<TAB>English, then <TAB>Portuguese)                    (2026-11-08)
 *   - a column copied from the work file in front: its clock (120<TAB>09:15<TAB>…), the number again
 *     (240<TAB>240<TAB>…), or the Hebrew line itself                                             (2026-11-15)
 *   - the work file's own separator: 900|48:07|English|Portuguese (174 replies)                   (2026-11-15)
 *   - the English, or the Portuguese, twice                                                       (2026-11-15)
 *   - a reply that stops, says "Wait — … let me redo" and writes the lines again: the later block wins
 * Only the range from…to counts; a line with the Divine Name written out is never good (it is asked again).
 */
export const NAME_RE = new RegExp(['\\u05d9\\u05d4\\u05d5\\u05d4', '\\bYa?hweh\\b', '\\bJeh?ov[aá]h?\\b', '\\bJeov[aá]\\b', '\\bY-?H-?[WV]-?H\\b'].join('|'), 'i')
const CLOCK = /^\d{1,2}:\d{2}(?::\d{2})?$/
const HEBREW = /[֐-׿]/
const LATIN = /[A-Za-z]/

export function readReply(text, from = null, to = null) {
  const rows = []
  let block = 0
  for (const raw of String(text || '').replace(/\r/g, '').split('\n')) {
    const line = raw.replace(/\s+$/, '')
    if (!line.trim()) continue
    let m = line.match(/^(\d+)\t(.+)$/)
    let sep = '\t'
    if (!m && !line.includes('\t')) {
      m = line.match(/^(\d+)\s*\|(.+)$/)
      sep = '|'
    }
    if (m) {
      const texts = m[2].split(sep).map((t) => t.trim()).filter(Boolean)
      if (texts.length >= 2 && CLOCK.test(texts[0])) texts.shift()
      if (texts.length === 3 && (texts[0] === m[1] || (HEBREW.test(texts[0]) && !LATIN.test(texts[0]) && !HEBREW.test(texts[1])))) texts.shift()
      if (texts.length === 3 && texts[0] === texts[1]) texts.shift()
      else if (texts.length === 3 && texts[1] === texts[2]) texts.pop()
      rows.push({ n: Number(m[1]), texts, block })
    } else if (/^\t/.test(line) && rows.length && rows[rows.length - 1].texts.length === 1) {
      // its own tabs split too: pushed whole, a half holding a tab gave the line four columns
      rows[rows.length - 1].texts.push(...line.split('\t').map((t) => t.trim()).filter(Boolean))
    } else if (rows.length) block++ // prose after some lines ("Wait — …", "Correction: …"): what follows replaces them
  }
  const inRange = (n) => from === null || (n >= from && n <= to)
  const good = new Map()
  const at = new Map() // the block each good line came from: a later block wins, inside a block the first line wins
  const en = new Map()
  for (const { n, texts, block: b } of rows) {
    if (!inRange(n)) continue
    if (texts.length === 2 && !NAME_RE.test(texts.join(' '))) {
      if (!good.has(n) || at.get(n) < b) {
        good.set(n, texts)
        at.set(n, b)
      }
    } else if (texts.length === 1 && !en.has(n) && !NAME_RE.test(texts[0])) en.set(n, texts[0])
  }
  for (const n of good.keys()) en.delete(n)
  return { good, en }
}
