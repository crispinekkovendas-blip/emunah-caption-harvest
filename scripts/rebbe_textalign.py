"""
rebbe_textalign.py — the Rebbe's own published Yiddish, timed to his voice by Meta MMS (2026-10-24, the owner:
"Ok" to the next test). The ears recover an unedited sicha only in half; for the sichos the Rebbe edited,
chabad.net has his text (Sefer HaSichos — open to the runners). Here that text is timed against the recording,
line by line, with the same forced aligner as align.py (torchaudio MMS_FA, Yiddish romanization).

  python scripts/rebbe_textalign.py --item rebbe-chabad --match REGEX --text-url URL --out out/textalign

1. the recording: archive.org item, the file whose name matches --match (every file name is printed);
2. the text: the page's sicha body (from "א." to before the footnotes), footnote numbers removed, cut into
   subtitle lines (≤ 90 characters, at punctuation);
3. the timing: groups of 8 lines, each aligned inside a window that starts where the previous group ended and is
   as long as the group should take to say (×2.5 + 40 s) — the first group searches the first 25 minutes, past the
   prayer and the blessings; a "*" at both ends absorbs what was said and is not in the text;
4. each group's mean token score is kept: the edited text is not word for word what was said, and a low score
   marks a stretch where they part.

Prints every line with its time and score, and writes out/textalign/aligned.json.
"""
import argparse
import html
import json
import os
import re
import statistics
import subprocess
import time
import urllib.parse
import urllib.request

UA = {'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
SR = 16000
GROUP = 8
CPS = 13.0  # characters of Yiddish text per second of the Rebbe's speech (rough; the window allows ×2.5)


def get(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
        data = r.read()
    return data if binary else data.decode('utf8', 'replace')


def recording(item, match, out):
    meta = json.loads(get(f'https://archive.org/metadata/{urllib.parse.quote(item)}'))
    files = [f for f in meta.get('files', []) if f.get('name', '').lower().endswith(('.mp4', '.mp3', '.webm', '.ogg', '.m4a', '.mkv'))]
    print(f'{item}: {len(files)} media files')
    for f in files:
        print(f'  {f["name"]}  ({f.get("length", "?")} s, {f.get("size", "?")} B)')
    pat = re.compile(match, re.I)
    hits = [f for f in files if pat.search(f['name'])]
    if not hits:
        raise SystemExit(f'no file matches {match!r}')
    f = min(hits, key=lambda f: int(f.get('size') or 1 << 40))
    url = f'https://archive.org/download/{urllib.parse.quote(item)}/{urllib.parse.quote(f["name"])}'
    print(f'\nrecording: {f["name"]}\n  {url}')
    raw = os.path.join(out, 'raw.bin')
    open(raw, 'wb').write(get(url, binary=True))
    wav = os.path.join(out, 'audio.wav')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', raw, '-vn', '-ac', '1', '-ar', str(SR), wav], check=True)
    os.remove(raw)
    return f['name'], url, wav


def sicha_lines(url):
    page = get(url)
    page = re.sub(r'(?s)<(script|style|nav|header|footer).*?</\1>', ' ', page)
    page = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</h\d>|</li>', '\n', page)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', page))
    t = re.sub(r'[ \t‎‏⁦-⁩]+', ' ', t)
    # the body: from the first section letter "א." to the editors' note / the addendum / the footnotes
    start = re.search(r'(?m)^\s*א\.\s', t)
    if not start:
        raise SystemExit('no "א." in the page')
    body = t[start.start():]
    end = re.search(r'(?m)^\s*(הוספה|הערות)\s*$|\[כ"ק אדמו"ר', body)
    body = body[: end.start()] if end else body
    body = re.sub(r'(?m)^\s*[א-ת]{1,2}\.\s', ' ', body)            # section letters
    body = re.sub(r'(?<=[^\d\s])\s+\d{1,3}\s*\*?(?=[\s.,:;)\]—–-])', '', body)  # footnote numbers
    body = re.sub(r'\s\d{1,3}\s', ' ', body)
    body = re.sub(r'\s+', ' ', body).strip()
    # subtitle lines: cut at punctuation, ≤ 90 characters
    pieces = re.split(r'(?<=[.:;,—–])\s+', body)
    lines, cur = [], ''
    for p in pieces:
        while len(p) > 90:  # a long clause: cut at the last space before 90
            k = p.rfind(' ', 0, 90)
            k = k if k > 30 else 90
            if cur:
                lines.append(cur)
                cur = ''
            lines.append(p[:k].strip())
            p = p[k:].strip()
        if cur and len(cur) + 1 + len(p) > 90:
            lines.append(cur)
            cur = p
        else:
            cur = (cur + ' ' + p).strip()
    if cur:
        lines.append(cur)
    return [l for l in lines if l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--item', default='rebbe-chabad')
    ap.add_argument('--match', required=True)
    ap.add_argument('--text-url', required=True)
    ap.add_argument('--out', default='out/textalign')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    os.environ.setdefault('SUPABASE_URL', 'http://unused')
    os.environ.setdefault('SUPABASE_SERVICE_KEY', 'unused')

    lines = sicha_lines(a.text_url)
    print(f'text: {len(lines)} lines, {sum(map(len, lines))} characters')
    for l in lines[:6]:
        print(f'  {l}')
    name, url, wav_path = recording(a.item, a.match, a.out)

    import numpy as np
    import soundfile as sf
    import torch

    import align as al

    wav, sr = sf.read(wav_path, dtype='float32')
    assert sr == SR
    dur = len(wav) / SR
    print(f'audio: {dur / 60:.1f} min')
    al.load()
    al.LCODE = 'yid'
    t0 = time.time()
    parts = []
    with torch.inference_mode():
        for s in range(0, len(wav), al.CHUNK * SR):
            x = torch.from_numpy(np.ascontiguousarray(wav[s: s + al.CHUNK * SR])).unsqueeze(0)
            if x.shape[1] < 400:
                continue
            e, _ = al.model(x)
            parts.append(e[0])
    emission = torch.cat(parts)
    fps = emission.shape[0] / dur
    print(f'emission: {emission.shape[0]} frames in {time.time() - t0:.0f}s')

    words = [al.words_of(l) for l in lines]
    cues = [None] * len(lines)
    scores = []
    cursor = None
    for g0 in range(0, len(lines), GROUP):
        idx = [i for i in range(g0, min(g0 + GROUP, len(lines))) if words[i]]
        if not idx:
            continue
        chars = sum(len(lines[i]) for i in idx)
        if cursor is None:
            ws, we = 0.0, min(dur, 25 * 60.0)
        else:
            ws, we = max(0.0, cursor - 3), min(dur, cursor + chars / CPS * 2.5 + 40)
        if we - ws < 5:
            break
        toks = ['*'] + [w for i in idx for w in words[i]] + ['*']
        try:
            spans = al.aligner(emission[int(ws * fps): int(we * fps)], al.tokenizer(toks))[1:-1]
        except Exception as err:
            print(f'group {g0}: {str(err)[:120]}')
            continue
        k, gscores = 0, []
        for i in idx:
            n = len(words[i])
            sp = spans[k: k + n]
            k += n
            cues[i] = [round(ws + sp[0][0].start / fps, 2), round(ws + sp[-1][-1].end / fps, 2)]
            gscores += [t.score for w in sp for t in w]
        g_score = statistics.mean(gscores) if gscores else 0
        scores.append({'from': g0, 'start': cues[idx[0]][0], 'end': cues[idx[-1]][1], 'score': round(g_score, 3)})
        cursor = cues[idx[-1]][1]
    print(f'aligned in {time.time() - t0:.0f}s')

    out = []
    for i, l in enumerate(lines):
        if cues[i]:
            g = next((s for s in scores if s['from'] <= i < s['from'] + GROUP), {'score': 0})
            out.append({'start': cues[i][0], 'end': cues[i][1], 'text': l, 'score': g['score']})
    med = statistics.median([s['score'] for s in scores]) if scores else 0
    doc = {'recording': name, 'url': url, 'text_url': a.text_url, 'duration': round(dur), 'lines': len(lines),
           'aligned': len(out), 'group_score_median': round(med, 3), 'groups': scores, 'cues': out}
    json.dump(doc, open(os.path.join(a.out, 'aligned.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    clock = lambda s: f'{int(s // 60):02d}:{s % 60:04.1f}'
    print(f'\n{len(out)}/{len(lines)} lines placed · group score median {med:.3f} '
          f'(scores are mean token probabilities; low = the text and the voice part)\n')
    for c in out:
        print(f'{clock(c["start"])}–{clock(c["end"])}  [{c["score"]:.2f}]  {c["text"]}')


if __name__ == '__main__':
    main()
