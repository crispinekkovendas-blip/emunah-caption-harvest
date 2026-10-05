/**
 * divine.ts — the Divine Name is never translated.
 *
 * When the speaker says "HaShem", the subtitle says "HaShem" — in every
 * language. Machine translation does not respect that on its own: measured
 * against Google's endpoint, "HaShem" survives into English and Spanish but
 * becomes השם or ה' in Hebrew and ХаШем in Russian, and — worst of all —
 * "Elokim" comes back as "Elohim" in French, undoing the very substitution
 * that spelling exists to make.
 *
 * So every protected term is masked before the text is sent and put back
 * verbatim afterwards. The placeholder (Xq1, Xq2…) was chosen by probing the
 * endpoint: it is the one short token that came back untouched in Hebrew,
 * English, Spanish, French and Russian.
 *
 * A leaf module: the prompts (server) and the translator both read from it.
 */

/**
 * Terms kept verbatim through translation. Latin transliterations only, plus
 * the unambiguous Hebrew abbreviation ה׳ — bare השם is left alone because it
 * also means "the name" in ordinary speech, and mistranslating that is worse
 * than translating it.
 */
const TERMS: RegExp[] = [
  /\bha[-\s]?shem\b/gi,
  /\bbaruch\s+ha[-\s]?shem\b/gi,
  /\badona[iyí]\b/gi,
  // no trailing \b: JS word boundaries are ASCII, so "Elokênu" would not close one
  /\belok[a-zÀ-ɏ]*/gi,
  /\bsha[dk]ai\b/gi,
  /(?<![֐-׿])ה['’׳](?=$|[\s.,;:!?)\]])/g,
]

/** The canonical spelling, for the prompts that ask Gemini to write it. */
export const CANONICAL = 'HaShem'

/**
 * The rule appended to every Gemini prompt that writes Portuguese: keep the
 * Name as the speaker said it. Kept here so the transcription, the summary and
 * the answers all say the same thing.
 */
export const DIVINE_PROMPT_RULE =
  'Nomes divinos: quando o orador disser HaShem, escreva exatamente HaShem — nunca troque por Deus, o Eterno, o Senhor, God ou Lord. O mesmo vale para Adonai, Elokim, Elokeinu e Shakai: escreva a palavra como ele a diz, em transliteração, sem traduzir e sem substituir por outro nome.'

/** a placeholder prefix that does not already appear in the texts */
function pickPrefix(texts: string[]): string {
  for (const p of ['Xq', 'Zq', 'Qx', 'Vq']) {
    if (!texts.some((t) => t.includes(p))) return p
  }
  return 'Xq'
}

export interface Masked {
  texts: string[]
  /** what each placeholder stands for, per text */
  slots: string[][]
  prefix: string
}

/** Replaces every protected term with a placeholder the translator leaves alone. */
export function maskDivine(texts: string[]): Masked {
  const prefix = pickPrefix(texts)
  const slots: string[][] = []
  const out = texts.map((text) => {
    const mine: string[] = []
    let s = text
    for (const re of TERMS) {
      s = s.replace(re, (m) => {
        mine.push(m)
        return `${prefix}${mine.length}`
      })
    }
    slots.push(mine)
    return s
  })
  return { texts: out, slots, prefix }
}

/**
 * Puts the terms back. Translators may change the placeholder's case or put a
 * space inside it, so the pattern is forgiving; a placeholder that did not come
 * back leaves the sentence as the translator wrote it.
 */
export function unmaskDivine(text: string, mine: string[], prefix: string): string {
  if (!mine.length) return text
  const re = new RegExp(`${prefix}\\s?(\\d{1,2})`, 'gi')
  return text.replace(re, (whole, n) => {
    const i = Number(n) - 1
    return i >= 0 && i < mine.length ? mine[i] : whole
  })
}

/** true when the text carries a term worth protecting (lets callers skip the work) */
export function hasDivine(text: string): boolean {
  return TERMS.some((re) => {
    re.lastIndex = 0
    return re.test(text)
  })
}
