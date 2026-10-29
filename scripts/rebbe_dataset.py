"""The Rebbe model, dataset step 5: the curated ✓ lines → audio clips + text for training (rebbe-train.yml).

2026-10-28 (the owner: "Go ahead, let's train this"; Kaggle, for the project's own use only — the Kaggle dataset
and model stay private). Input: the ears-<chunk> artifacts of rebbe-ears.yml, one folder each (clip-raw.opus =
the original audio, curated.json = Claude's lines). Only ✓ lines and lines the Hebrew ear verified (rebbe_curate.check) are used; neighbours closer than 1 s join into
one example of at most 25 s (Whisper hears 30 s). Whole chunks go to dev (1 in 9 by a hash of the name: 5 of the 52 chunks) so nothing of a
dev chunk is trained on. The test set is the "Lubavitcher Rebbe Lexicon" on archive.org: 40 clips of the Rebbe
(1981) whose file names are his words verbatim, romanized — Claude writes them once in Yiddish letters; they are
never trained on.

    python scripts/rebbe_dataset.py --ears out/ears-all --out out/dataset [--no-test]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

SR = 16000
MAX = 25.0
GAP = 1.0
PAD = 0.2
LEXICON = 'Lubavitcher_Rebbe'
MEDIA = ('.mp3', '.ogg', '.oga', '.wav', '.flac', '.m4a', '.mp4', '.webm', '.opus')


def examples(curated):
    sure = sorted((l for l in curated['lines'] if l['mark'] == '✓' or l.get('verified')), key=lambda l: l['start'])
    out, cur = [], None
    for l in sure:
        if cur and l['start'] - cur['end'] <= GAP and l['end'] - cur['start'] <= MAX:
            cur['end'] = l['end']
            cur['text'] += ' ' + l['text']
        else:
            if cur:
                out.append(cur)
            cur = {'start': l['start'], 'end': l['end'], 'text': l['text']}
    if cur:
        out.append(cur)
    return [e for e in out if 1.0 <= e['end'] - e['start'] <= MAX + 5]


def cut(src, start, end, dst):
    s = max(0.0, start - PAD)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{s:.2f}', '-t', f'{end + PAD - s:.2f}', '-i', src,
                    '-ac', '1', '-ar', str(SR), '-c:a', 'flac', dst], check=True)


def is_dev(chunk_id):
    return int(hashlib.sha1(chunk_id.encode()).hexdigest(), 16) % 9 == 0


def build(ears, out):
    stats = {'train': [0, 0.0], 'dev': [0, 0.0]}
    meta = {k: open(os.path.join(out, k, 'metadata.jsonl'), 'w', encoding='utf8') for k in stats}
    # a folder per chunk — straight under --ears (ears-<chunk> artifacts) or deeper (the ears-bundle of rebbe-curate.yml)
    dirs = sorted({r for r, _, fs in os.walk(ears) if 'clip-raw.opus' in fs or 'curated.json' in fs})
    for d in dirs:
        name = os.path.basename(d)
        cj, audio = os.path.join(d, 'curated.json'), os.path.join(d, 'clip-raw.opus')
        if not (os.path.exists(cj) and os.path.exists(audio)):
            print(f'  {name}: no curated.json / clip-raw.opus — skipped')
            continue
        cur = json.load(open(cj, encoding='utf8'))
        cid = cur['source'].get('id') or name
        split = 'dev' if is_dev(cid) else 'train'
        ex = examples(cur)
        for i, e in enumerate(ex):
            fn = f'{cid}-{i:04d}.flac'
            cut(audio, e['start'], e['end'], os.path.join(out, split, fn))
            dur = round(e['end'] - e['start'] + 2 * PAD, 2)
            meta[split].write(json.dumps({'file_name': fn, 'text': e['text'], 'duration': dur, 'chunk': cid},
                                         ensure_ascii=False) + '\n')
            stats[split][0] += 1
            stats[split][1] += dur
        print(f'  {cid}: {len(ex)} examples → {split}')
    for f in meta.values():
        f.close()
    return stats


def lexicon(out):
    """the test set: the Lexicon clips; their romanized names → Yiddish letters by Claude (once, in one request)"""
    meta = json.load(urllib.request.urlopen(f'https://archive.org/metadata/{LEXICON}', timeout=60))
    clips = [f for f in meta.get('files', []) if f.get('name', '').lower().endswith(MEDIA)
             and f.get('source') == 'original']
    if not clips:
        clips = [f for f in meta.get('files', []) if f.get('name', '').lower().endswith('.mp3')]
    rows = []
    for f in clips:
        roman = re.sub(r'^.*?1981\s*-\s*', '', os.path.splitext(f['name'])[0]).strip()
        if roman:
            rows.append((f['name'], roman))
    numbered = '\n'.join(f'{i + 1}\t{r}' for i, (_, r) in enumerate(rows))
    ask = ('These are verbatim transcripts of the Lubavitcher Rebbe speaking Yiddish, in YIVO-style romanization '
           '(loshon-kodesh words romanized as pronounced: "emune", "toyre", "mitsves", "hahanhoge"). Write each in '
           'Yiddish in Hebrew letters, standard Chabad spelling as in Sefer HaSichos: Germanic words with אַ אָ וו יי '
           '(אַז, וואָס, גלייבט), loshon-kodesh words in their Hebrew spelling (אמונה, תורה, מצוות, ההנהגה). English '
           'words he used stay as he said them, in Yiddish letters (טראַסט). Same words, same order, nothing added. '
           'Reply with ONLY lines: number<TAB>Yiddish.')
    r = subprocess.run(['claude', '-p', ask, '--tools', '', '--model', 'sonnet', '--output-format', 'json'],
                       input=numbered, capture_output=True, text=True, timeout=1800)
    yid = {}
    try:
        reply = str(json.loads(r.stdout).get('result') or '')
    except json.JSONDecodeError:
        reply = ''
        print(f'Claude did not answer for the test set: {(r.stderr or r.stdout)[:300]}')
    # run 40791837255 matched none of the lines with a tab only: number, then a tab / dot / bracket / spaces
    for l in reply.splitlines():
        m = re.match(r'^\s*(\d+)\s*[\t.):|\-]?\s*(.*[\u05D0-\u05EA].*?)\s*$', l)
        if m:
            yid[int(m.group(1))] = m.group(2).strip()
    if reply and not yid:
        print('Claude answered, but no line could be read:\n' + reply[:1500])
    n = 0
    with open(os.path.join(out, 'test', 'metadata.jsonl'), 'w', encoding='utf8') as m:
        for i, (name, roman) in enumerate(rows):
            if i + 1 not in yid:
                continue
            src = os.path.join(out, 'test', 'src.bin')
            url = f'https://archive.org/download/{LEXICON}/{urllib.parse.quote(name)}'
            open(src, 'wb').write(urllib.request.urlopen(url, timeout=120).read())
            fn = f'lexicon-{i:02d}.flac'
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src, '-ac', '1', '-ar', str(SR), '-c:a', 'flac',
                            os.path.join(out, 'test', fn)], check=True)
            os.remove(src)
            m.write(json.dumps({'file_name': fn, 'text': yid[i + 1], 'roman': roman}, ensure_ascii=False) + '\n')
            n += 1
    print(f'test (Lexicon): {n}/{len(rows)} clips')
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ears', required=True)
    ap.add_argument('--out', default='out/dataset')
    ap.add_argument('--no-test', action='store_true')
    a = ap.parse_args()
    for k in ('train', 'dev', 'test'):
        os.makedirs(os.path.join(a.out, k), exist_ok=True)
    stats = build(a.ears, a.out)
    n_test = 0 if a.no_test else lexicon(a.out)
    summary = {k: {'examples': v[0], 'hours': round(v[1] / 3600, 2)} for k, v in stats.items()}
    summary['test'] = {'examples': n_test}
    json.dump(summary, open(os.path.join(a.out, 'summary.json'), 'w'), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
