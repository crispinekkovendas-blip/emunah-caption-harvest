"""
align.py — retime a lesson's Hebrew subtitle lines against its audio with Meta's MMS forced aligner
(torchaudio MMS_FA), on GitHub's CPU runners (2026-10-14, the owner: subtitles 4–5 lines ahead of the
voice in some lessons).

  python scripts/align.py --ids ID[,ID…] [--publish]

For each lesson: the transcript row from Supabase → the audio (yt-dlp, 16 kHz mono) → the model's
emission over the whole lesson, 30 s at a time → the existing Hebrew lines aligned in small groups, each
inside a window around where the line is now (± a margin, a "*" wildcard at both ends so speech of the
neighbours is absorbed); each group's measured shift moves the next window, so a drift that builds up
is followed. The WORDS never change, only start/end, so the pt/en translations (one text per Hebrew
line) stay valid. --publish writes the new times to the row and keeps the old ones in `cuesOrig`.
A report per lesson goes to out/align/<id>.json.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import tempfile
import time
import urllib.request

import numpy as np
import soundfile as sf
import torch
import uroman as ur
from torchaudio.pipelines import MMS_FA as bundle

GROUP = 12  # lines per alignment window
MARGIN = 25.0  # seconds of slack on each side of a window
CHUNK = 30  # seconds of audio per model pass
SR = 16000

SUPA = os.environ['SUPABASE_URL'].rstrip('/')
KEY = os.environ['SUPABASE_SERVICE_KEY']
H = {'apikey': KEY, 'authorization': f'Bearer {KEY}'}


def kv_get(key):
    q = urllib.parse.quote(key, safe='')
    req = urllib.request.Request(f'{SUPA}/rest/v1/global_options?select=value&key=eq.{q}', headers=H)
    rows = json.load(urllib.request.urlopen(req, timeout=60))
    if not rows:
        return None
    v = rows[0]['value']
    return json.loads(v) if isinstance(v, str) else v


def kv_put(key, value):
    body = json.dumps([{'key': key, 'value': json.dumps(value, ensure_ascii=False), 'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}]).encode()
    req = urllib.request.Request(
        f'{SUPA}/rest/v1/global_options?on_conflict=key',
        data=body,
        method='POST',
        headers={**H, 'content-type': 'application/json', 'prefer': 'resolution=merge-duplicates,return=minimal'},
    )
    urllib.request.urlopen(req, timeout=60)


def audio_of(vid, tmp):
    out = os.path.join(tmp, f'{vid}.wav')
    # YouTube refuses GitHub's runners ("Sign in to confirm you're not a bot"): the audio is downloaded
    # on the owner's computer and handed over through the draft release align-queue → audio/<id>.opus
    local = os.path.join('audio', f'{vid}.opus')
    if os.path.exists(local):
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', local, '-ac', '1', '-ar', str(SR), out], check=True)
    else:
        _youtube(vid, tmp)
    wav, sr = sf.read(out, dtype='float32')
    os.remove(out)
    assert sr == SR, sr
    return wav.mean(axis=1) if wav.ndim > 1 else wav


def _youtube(vid, tmp):
    subprocess.run(
        ['python', '-m', 'yt_dlp', '-q', '--no-warnings', '-f', 'bestaudio', '-x', '--audio-format', 'wav',
         '--postprocessor-args', f'ffmpeg:-ac 1 -ar {SR}', '-o', os.path.join(tmp, f'{vid}.%(ext)s'),
         f'https://www.youtube.com/watch?v={vid}'],
        check=True,
    )


model = tokenizer = aligner = DICT = uro = None


def load():
    global model, tokenizer, aligner, DICT, uro
    model = bundle.get_model()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()
    DICT = bundle.get_dict()
    uro = ur.Uroman()


# uroman's language for the lesson being aligned: Hebrew, or Yiddish (the Rebbe's sichos, 2026-10-24 —
# same letters, but װ ײ ױ and the pointed alefs are read the Yiddish way)
LCODE = 'heb'


def words_of(text):
    r = uro.romanize_string(text, lcode=LCODE).lower()
    r = re.sub(r"[’`]", "'", r)
    out = []
    for w in r.split():
        w = ''.join(ch for ch in w if ch in DICT and ch != '*')
        if w:
            out.append(w)
    return out


def align(cues, wav):
    dur = len(wav) / SR
    parts = []
    with torch.inference_mode():
        for s in range(0, len(wav), CHUNK * SR):
            x = torch.from_numpy(np.ascontiguousarray(wav[s : s + CHUNK * SR])).unsqueeze(0)
            if x.shape[1] < 400:
                continue
            e, _ = model(x)
            parts.append(e[0])
    emission = torch.cat(parts)
    fps = emission.shape[0] / dur
    lines = [words_of(c[2]) for c in cues]
    new = [None] * len(cues)
    shift = 0.0
    groups = []
    for g0 in range(0, len(cues), GROUP):
        idx = [i for i in range(g0, min(g0 + GROUP, len(cues))) if lines[i]]
        if not idx:
            continue
        ws = max(0.0, cues[idx[0]][0] + shift - MARGIN)
        we = min(dur, cues[idx[-1]][1] + shift + MARGIN)
        words = ['*'] + [w for i in idx for w in lines[i]] + ['*']
        try:
            spans = aligner(emission[int(ws * fps) : int(we * fps)], tokenizer(words))[1:-1]
        except Exception as err:
            groups.append({'t': cues[g0][0], 'error': str(err)[:120]})
            continue
        k = 0
        deltas = []
        for i in idx:
            n = len(lines[i])
            sp = spans[k : k + n]
            k += n
            new[i] = [ws + sp[0][0].start / fps, ws + sp[-1][-1].end / fps]
            deltas.append(new[i][0] - cues[i][0])
        shift = statistics.median(deltas)
        groups.append({'t': round(cues[g0][0], 1), 'shift': round(shift, 2)})
    # lines that could not be aligned take the shift of the line before; then no overlaps, short gaps closed
    for i, c in enumerate(cues):
        if new[i] is None:
            prev = next((j for j in range(i - 1, -1, -1) if new[j]), None)
            sh = (new[prev][0] - cues[prev][0]) if prev is not None else 0.0
            new[i] = [c[0] + sh, c[1] + sh]
    out = []
    for i, c in enumerate(cues):
        st = max(new[i][0], out[-1][0] + 0.05 if out else 0.0)
        nxt = new[i + 1][0] if i + 1 < len(cues) else dur
        en = max(st + 0.3, min(max(new[i][1], st + 0.3), nxt))
        out.append([round(st, 2), round(en, 2), c[2]])
    for i in range(len(out) - 1):
        if out[i + 1][0] - out[i][1] < 1.5:
            out[i][1] = out[i + 1][0]
    return out, groups, dur


def main():
    global LCODE
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', required=True)
    ap.add_argument('--publish', action='store_true')
    a = ap.parse_args()
    os.makedirs('out/align', exist_ok=True)
    t0 = time.time()
    load()
    print(f'model loaded in {time.time() - t0:.0f}s')
    for vid in [x.strip() for x in a.ids.split(',') if x.strip()]:
        t1 = time.time()
        row = kv_get(f'videos/transcript/{vid}')
        if not row or not row.get('cues'):
            print(f'{vid}: no transcript')
            continue
        LCODE = 'yid' if row.get('lang') == 'yi' else 'heb'
        old = row.get('cuesOrig') or row['cues']  # always align the ORIGINAL times
        with tempfile.TemporaryDirectory() as tmp:
            wav = audio_of(vid, tmp)
        t2 = time.time()
        new, groups, dur = align(old, wav)
        t3 = time.time()
        d = [n[0] - o[0] for n, o in zip(new, old)]
        rep = {
            'id': vid,
            'duration': round(dur),
            'lines': len(old),
            'download_s': round(t2 - t1),
            'align_s': round(t3 - t2),
            'shift_median': round(statistics.median(d), 2),
            'shift_p10': round(float(np.percentile(d, 10)), 2),
            'shift_p90': round(float(np.percentile(d, 90)), 2),
            'groups': groups,
            'cues': new,
        }
        json.dump(rep, open(f'out/align/{vid}.json', 'w', encoding='utf8'), ensure_ascii=False)
        print(f'{vid}: {dur / 60:.0f} min audio, download {t2 - t1:.0f}s, align {t3 - t2:.0f}s — shift median {rep["shift_median"]:+.2f}s (p10 {rep["shift_p10"]:+.2f}, p90 {rep["shift_p90"]:+.2f})')
        for g in groups[:: max(1, len(groups) // 30)]:
            print(f'   {int(g["t"] // 60):3d}:{int(g["t"] % 60):02d}  {g.get("shift", g.get("error"))}')
        if a.publish:
            row['cuesOrig'] = old
            row['cues'] = new
            row['aligned'] = {'by': 'mms_fa', 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'shift': rep['shift_median']}
            kv_put(f'videos/transcript/{vid}', row)
            print(f'{vid}: published')


if __name__ == '__main__':
    import urllib.parse  # noqa: F401  (kv_get)

    main()
