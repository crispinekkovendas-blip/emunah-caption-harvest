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
 *   - a reply that stops, says "Wait — … let me redo" and writes the lines again: the later block wins, and the lines
 *     before such a note are never kept, even when no new block follows (they are asked again)
 * Only the range from…to counts; a line with the Divine Name written out is never good (it is asked again).
 */
export const NAME_RE = new RegExp(['\\u05d9\\u05d4\\u05d5\\u05d4', '\\bYa?hweh\\b', '\\bJeh?ov[aá]h?\\b', '\\bJeov[aá]\\b', '\\bY-?H-?[WV]-?H\\b'].join('|'), 'i')
// 2026-11-15 (the ten-lane test): a note in which Claude takes back what it wrote ("Wait — my numbering above drifted",
// "Hmm — I need to correct…"). 1,605 of 42,961 saved replies hold one; in 479 nothing follows it. Tuned on all of them:
// it matches 1,600, and not the translation lines that merely contain "wait" or "mistake".
const RETRACT =
  /^\W*(?:<think>|thinking:|wait\b|hmm\b|hold on|oops|sorry|correction|reconsider|actually,? (?:i|the|my|lines?)\b|let me (?:redo|re-do|correct|fix|restate|re-?emit|re-?write|recheck|reconsider|restart|start over)|let me (?:just )?(?:produce|provide|give|do|write|output) (?:the|this|all|it|them)\b|(?:i )?(?:need|must|have) to (?:correct|fix|redo|re-?emit|restate|re-?output|output|produce|restart|stop|be careful)|i (?:must|need) (?:output|produce|correct|fix|redo)|i must correct|i made (?:an?|some) (?:error|mistake)|i mis|i got the (?:format|numbering|lines?) wrong|error$)/i
// a note about the whole block, whatever numbers it names
const WHOLE =
  /drift|shift|numbering|number(?:ed|s)? wrong|mis-?number|mismatched (?:the )?line numbers|recount|misalign|format|placeholder|everything|whole|entire|all (?:the )?lines|restart|start over|malformed|duplicate|\bthe above\b|output above/i
const WORDS = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10 }
/** the line numbers a taking-back note names (a Set), or null when it is about everything written so far */
function namedLines(note, rows) {
  if (WHOLE.test(note)) return null
  const text = note.replace(/\d{1,2}:\d{2}(?::\d{2})?/g, ' ') // clocks are not line numbers
  const set = new Set()
  let any = false
  for (const m of text.matchAll(/(\d+)\s*(?:–|—|-|to|through)\s*(\d+)/g)) {
    any = true
    for (let i = +m[1]; i <= +m[2] && i - +m[1] <= 2000; i++) set.add(i)
  }
  for (const m of text.matchAll(/(?:from|after)\s+(?:line\s+)?(\d+)|(\d+)\s+onwards?/g)) {
    any = true
    const s = +(m[1] || m[2])
    for (const r of rows) if (r.n >= s) set.add(r.n)
  }
  const last = text.match(/last\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*lines?/i)
  if (last) {
    any = true
    const k = last[1] ? WORDS[last[1].toLowerCase()] || +last[1] : 1
    for (const r of rows.slice(-k)) set.add(r.n)
  }
  for (const m of text.matchAll(/\b(\d+)\b/g)) {
    any = true
    set.add(+m[1])
  }
  return any ? set : null
}
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
    } else if (rows.length) {
      // prose after some lines: what follows replaces them; when the prose takes them back ("Wait — the numbering
      // above drifted"), the lines written so far are dropped, even if nothing follows — they are asked again
      // (aQGm8epS9Bw, 2026-11-15: line 122 kept the text of line 121 from a reply that said "I need to correct that").
      // A note that names its lines ("I need to fix one thing: line 599 …", "lines 442–449") drops only those, unless
      // it speaks of drift, shifted numbering or format — then all of them.
      if (RETRACT.test(line.trim())) {
        const named = namedLines(line, rows)
        for (const r of rows) if (!named || named.has(r.n)) r.dropped = true
      }
      block++
    }
  }
  const inRange = (n) => from === null || (n >= from && n <= to)
  const good = new Map()
  const at = new Map() // the block each good line came from: a later block wins, inside a block the first line wins
  const en = new Map()
  for (const { n, texts, block: b, dropped } of rows) {
    if (!inRange(n) || dropped) continue
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
