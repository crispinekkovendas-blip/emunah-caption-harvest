"""The Rebbe model, dataset step 2: check the published text's timing with an independent ear.

2026-10-24 (the owner: "Ok do it"). rebbe_textalign.py placed every line of Sefer HaSichos on the recording
with Meta MMS — but MMS always places every line, and its score did not tell a right text from a wrong one
(a Hebrew rendering scored above the right Yiddish). Here ivrit.ai (WhisperX, Hebrew) hears the recording on
its own, and each published line is compared with what it heard in the seconds MMS gave the line.

The comparison is on the consonant skeleton (no vowel letters, no niqqud, final letters folded: Yiddish and
Hebrew spell the same word differently) — the share of the line's letter triples the ear also heard there.
The same line against the ear's words at shifted times (±45…300 s) is the chance level: a line is kept only
when its own place beats every shift of its own and the chance level of the whole talk (95th percentile).

    python scripts/rebbe_verify.py --aligned aligned.json --item rebbe-chabad --match '^29_…' --out out/verify
"""
import argparse
import json
import os
import re
import statistics
import time

SHIFTS = (-300, -180, -120, -75, -45, 45, 75, 120, 180, 300)
PAD = 2.0  # seconds of slack around MMS's span
FINALS = str.maketrans('ךםןףץ', 'כמנפצ')


def skeleton(text):
    t = re.sub(r'[֑-ׇ]', '', text)          # niqqud, cantillation, Yiddish points
    t = t.replace('ײ', '').replace('ױ', '').replace('װ', '').translate(FINALS)
    t = re.sub(r'[^א-ת ]', ' ', t)
    t = re.sub(r'[אעויה]', '', t)                     # vowel letters: Yiddish writes them, Hebrew often not
    return re.sub(r'\s+', '', t)


def grams(text):
    s = skeleton(text)
    return {s[i:i + 3] for i in range(len(s) - 2)}


def heard(words, start, end):
    return ' '.join(w for s, e, w in words if e >= start - PAD and s <= end + PAD)


def overlap(line_grams, text):
    if not line_grams:
        return 0.0
    return len(line_grams & grams(text)) / len(line_grams)


def ear(wav_path, out):
    """ivrit.ai through WhisperX with the word aligner; no vocabulary prompt (it recites the prompt in pauses,
    which would make false matches), the anti-loop options of the four-ears run."""
    os.environ.setdefault('SUPABASE_URL', 'http://unused')
    os.environ.setdefault('SUPABASE_SERVICE_KEY', 'unused')
    import whisperx
    from rebbe_test import ANTI_LOOP, PASSES
    from transcribe import load_wav

    model_name, align_lang = PASSES['he']
    wav = load_wav(wav_path)
    t = time.time()
    model = None
    for extra in ({'vad_method': 'silero', 'asr_options': dict(ANTI_LOOP)}, {'asr_options': dict(ANTI_LOOP)}, {}):
        try:
            model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language='he', **extra)
            print(f'WhisperX: {model_name} with {sorted(extra)}')
            break
        except (TypeError, ValueError) as err:
            print(f'WhisperX load_model {sorted(extra)} refused: {err}')
    res = model.transcribe(wav, batch_size=8, language='he')
    print(f'ASR {time.time() - t:.0f}s for {len(wav) / 16000 / 60:.1f} min')
    am, meta = whisperx.load_align_model(language_code=align_lang, device='cpu')
    al = whisperx.align(res['segments'], am, meta, wav, 'cpu', return_char_alignments=False)
    words = []
    for sg in al['segments']:
        for w in sg.get('words', []):
            if (w.get('word') or '').strip():
                s, e = w.get('start', sg['start']), w.get('end', sg['end'])
                words.append([round(s, 2), round(e, 2), w['word'].strip()])
    json.dump({'model': model_name, 'words': words}, open(os.path.join(out, 'ear-he.json'), 'w', encoding='utf8'),
              ensure_ascii=False)
    print(f'{len(words)} words heard; ASR + align {time.time() - t:.0f}s')
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aligned', required=True)
    ap.add_argument('--item', default='rebbe-chabad')
    ap.add_argument('--match', required=True)
    ap.add_argument('--out', default='out/verify')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    from rebbe_textalign import recording

    doc = json.load(open(a.aligned, encoding='utf8'))
    cues = doc['cues']
    print(f'{doc.get("recording")}: {len(cues)} placed lines from {doc.get("text_url")}')
    _, _, wav = recording(a.item, a.match, a.out)
    words = ear(wav, a.out)
    dur = doc.get('duration') or (words[-1][1] if words else 0)

    rows, null = [], []
    for c in cues:
        g = grams(c['text'])
        own = overlap(g, heard(words, c['start'], c['end']))
        shifted = [overlap(g, heard(words, c['start'] + d, c['end'] + d))
                   for d in SHIFTS if 0 <= c['start'] + d and c['end'] + d <= dur]
        null += shifted
        rows.append({**c, 'ear': heard(words, c['start'], c['end']), 'overlap': round(own, 3),
                     'best_shift': round(max(shifted), 3) if shifted else 0.0})
    level = statistics.quantiles(null, n=20)[-1] if len(null) >= 20 else 1.0
    kept = [r for r in rows if r['overlap'] > level and r['overlap'] > r['best_shift']]
    for r in rows:
        r['kept'] = r in kept
    secs = sum(r['end'] - r['start'] for r in kept)

    clock = lambda s: f'{int(s // 60):02d}:{s % 60:04.1f}'
    print(f'\nchance level (95th percentile of the shifted places): {level:.3f}')
    print(f'median overlap at MMS\'s place: {statistics.median(r["overlap"] for r in rows):.3f} · '
          f'at the shifted places: {statistics.median(null):.3f}')
    print(f'kept {len(kept)}/{len(rows)} lines · {secs / 60:.1f} min of speech\n')
    for r in rows:
        mark = '✓' if r['kept'] else ' '
        print(f'{mark} {clock(r["start"])}–{clock(r["end"])}  own {r["overlap"]:.2f} · shift {r["best_shift"]:.2f}  {r["text"]}')
        print(f'      ear: {r["ear"][:160]}')
    json.dump({'recording': doc.get('recording'), 'text_url': doc.get('text_url'), 'chance_level': round(level, 3),
               'kept_lines': len(kept), 'kept_seconds': round(secs), 'lines': rows},
              open(os.path.join(a.out, 'verified.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)


if __name__ == '__main__':
    main()
