/**
 * batch-reply.mjs — turn one Claude reply into a piece's output file (2026-11-08).
 *
 *   node scripts/batch-reply.mjs usage.json in.txt out.txt merged.json en.txt [final]
 *
 * The old filter accepted exactly N<TAB>English<TAB>Portuguese and silently dropped anything else, so a
 * stray tab at the end of a line — a fully translated line — became "lines missing" at publish and the
 * whole lesson was thrown away (about 27,400 pieces by 2026-11-08). Here the line is read tolerantly,
 * only the piece's own range counts, and good lines are kept from one try to the next.
 * out.txt is written when the range is complete, or with whatever there is when `final` is given.
 * A reply that is English only goes to en.txt, for the workflow to ask the Portuguese separately.
 */
import fs from 'node:fs'

const [usageFile, inFile, outFile, mergedFile, enFile, final] = process.argv.slice(2)
let j = {}
try {
  j = JSON.parse(fs.readFileSync(usageFile, 'utf8'))
} catch {}
const head = fs.readFileSync(inFile, 'utf8').match(/traduzir as linhas (\d+) a (\d+)/)
const a = head ? Number(head[1]) : null
const b = head ? Number(head[2]) : null
const inRange = (n) => a === null || (n >= a && n <= b)

const good = new Map(fs.existsSync(mergedFile) ? JSON.parse(fs.readFileSync(mergedFile, 'utf8')) : [])
const en = new Map()
const rows = []
if (!j.is_error) {
  for (const raw of String(j.result || '').split('\n')) {
    const line = raw.replace(/\s+$/, '')
    if (!line.trim()) continue
    const number = line.match(/^(\d+)\t(.+)$/)
    if (number) rows.push({ n: Number(number[1]), texts: number[2].split('\t').map((t) => t.trim()).filter(Boolean) })
    // a line split in two: N<TAB>English, then <TAB>Portuguese
    else if (/^\t/.test(line) && rows.length && rows[rows.length - 1].texts.length === 1) rows[rows.length - 1].texts.push(line.trim())
  }
}
for (const { n, texts } of rows) {
  if (!inRange(n)) continue
  if (texts.length === 2 && !good.has(n)) good.set(n, texts)
  else if (texts.length === 1 && !en.has(n)) en.set(n, texts[0])
}

const wanted = a === null ? [...good.keys()] : Array.from({ length: b - a + 1 }, (_, i) => a + i)
const missing = wanted.filter((n) => !good.has(n)).length
fs.writeFileSync(mergedFile, JSON.stringify([...good]))
if (!good.size && en.size) fs.writeFileSync(enFile, [...en].sort((x, y) => x[0] - y[0]).map(([n, t]) => `${n}\t${t}`).join('\n') + '\n')
if (good.size && (!missing || final)) {
  fs.writeFileSync(outFile, [...good].sort((x, y) => x[0] - y[0]).map(([n, [e, p]]) => `${n}\t${e}\t${p}`).join('\n') + '\n')
}
console.log(`reply: ${good.size} good lines, ${missing} missing, ${en.size} English-only${j.is_error ? ' · error: ' + String(j.result).slice(0, 120) : ''}`)
