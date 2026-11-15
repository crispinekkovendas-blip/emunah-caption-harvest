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
 * When some lines are good and some are still missing, their numbers go to merged.missing (2026-11-15).
 * With a usage file that does not exist (`-`), it only writes out.txt from merged.json (the last word of a job).
 */
import fs from 'node:fs'
import { readReply } from './reply-lines.mjs'

const [usageFile, inFile, outFile, mergedFile, enFile, final] = process.argv.slice(2)
let j = {}
try {
  j = JSON.parse(fs.readFileSync(usageFile, 'utf8'))
} catch {}
const head = fs.readFileSync(inFile, 'utf8').match(/traduzir as linhas (\d+) a (\d+)/)
const a = head ? Number(head[1]) : null
const b = head ? Number(head[2]) : null

// good lines are kept from one try to the next: a later try only fills what is still missing
const good = new Map(fs.existsSync(mergedFile) ? JSON.parse(fs.readFileSync(mergedFile, 'utf8')) : [])
// the reading itself (stray tabs, split lines, copied columns, pipes, a reply that redoes itself, the Divine Name)
// is in scripts/reply-lines.mjs, shared with scripts/batch-salvage.mjs
const reply = j.is_error ? { good: new Map(), en: new Map() } : readReply(j.result, a, b)
for (const [n, texts] of reply.good) if (!good.has(n)) good.set(n, texts)
const en = new Map([...reply.en].filter(([n]) => !good.has(n)))

const wanted = a === null ? [...good.keys()] : Array.from({ length: b - a + 1 }, (_, i) => a + i)
const gone = wanted.filter((n) => !good.has(n))
const missing = gone.length
fs.writeFileSync(mergedFile, JSON.stringify([...good]))
// 2026-11-15: the numbers still missing, for the workflow to ask ONLY those again (half of the incomplete replies
// lacked 1–5 lines of 120, and the second try translated all 120 again)
// merged.retry.txt is the work file for that request: the same study and context, the lines of this part already
// translated shown as context, and under LINHAS A TRADUZIR only the missing ones
const missingFile = mergedFile.replace(/\.json$/, '') + '.missing'
const retryFile = mergedFile.replace(/\.json$/, '') + '.retry.txt'
if (good.size && missing && head) {
  fs.writeFileSync(missingFile, gone.join(', ') + '\n')
  const [top, body = ''] = fs.readFileSync(inFile, 'utf8').replace(/\r/g, '').split('LINHAS A TRADUZIR:\n')
  const want = new Set(gone)
  const lines = body.split('\n').filter((l) => /^\d+\|/.test(l))
  fs.writeFileSync(
    retryFile,
    top.replace(/traduzir as linhas \d+ a \d+ \(\d+ linhas\)/, `faltam ${missing} linhas desta parte: ${gone.join(', ')}`).replace(/\n*$/, '\n\n') +
      'LINHAS DESTA PARTE JÁ TRADUZIDAS (só contexto, NÃO traduzir):\n' +
      lines.filter((l) => !want.has(Number(l.split('|')[0]))).join('\n') +
      '\n\nLINHAS A TRADUZIR:\n' +
      lines.filter((l) => want.has(Number(l.split('|')[0]))).join('\n') +
      '\n',
  )
} else {
  fs.rmSync(missingFile, { force: true })
  fs.rmSync(retryFile, { force: true })
}
if (!good.size && en.size) fs.writeFileSync(enFile, [...en].sort((x, y) => x[0] - y[0]).map(([n, t]) => `${n}\t${t}`).join('\n') + '\n')
if (good.size && (!missing || final)) {
  fs.writeFileSync(outFile, [...good].sort((x, y) => x[0] - y[0]).map(([n, [e, p]]) => `${n}\t${e}\t${p}`).join('\n') + '\n')
}
console.log(`reply: ${good.size} good lines, ${missing} missing, ${en.size} English-only${j.is_error ? ' · error: ' + String(j.result).slice(0, 120) : ''}`)
