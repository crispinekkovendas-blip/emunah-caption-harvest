"""
dub.py — a Portuguese and an English dub of each curated lesson with Kokoro-82M (open source, CPU),
on GitHub's runners (2026-10-15, the owner: "run on github public option 2 right away and store here
on disk E").

  python scripts/dub.py --lane N --lanes 8 [--budget-min 300] [--ids a,b]

Lessons: the Shiur Hebraico catalogue (/app/catalogo/) — this week's parashá first, then the newest —
the lane's share by a hash of the id, minus the ones already done (dub/done/<id>). For each lesson:
/legendas/?v=<id> (Hebrew cues + pt + en, one text per cue); the lines are joined into sentences
(at most 4 lines / 240 characters), each sentence is spoken where its first line starts and, when it is
longer than its slot, spoken again faster (up to 1.45×); a sentence that still overruns pushes the next
one later. Output: out/dub/<id>.pt.opus, <id>.en.opus (mono, 24 kHz, 32 kb/s) + <id>.json (where each
sentence was placed). The workflow hands them to the draft release dub-queue; the owner's computer
takes them to E:\\shiur-dub and empties the queue.
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request

import numpy as np
import soundfile as sf

BASE = 'https://shiur-hebraico.vercel.app'
SR = 24000
VOICES = {'pt': ('p', 'pm_alex'), 'en': ('a', 'am_michael')}
MAX_SPEED = 1.45


def get_json(path):
    req = urllib.request.Request(BASE + path, headers={'user-agent': 'shiur-dub/1'})
    return json.load(urllib.request.urlopen(req, timeout=120))


def lane_of(vid, lanes):
    h = 7
    for ch in vid:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % lanes


def sentences(cues, texts):
    """join lines into sentences: [start, slot_end, text]"""
    out = []
    cur = None
    for i, (c, t) in enumerate(zip(cues, texts)):
        t = (t or '').strip()
        if not t:
            continue
        if cur is None:
            cur = {'s': c[0], 'e': c[1], 'text': t, 'n': 1}
        else:
            cur['text'] += ' ' + t
            cur['e'] = c[1]
            cur['n'] += 1
        nxt = cues[i + 1][0] if i + 1 < len(cues) else c[1]
        cur['e'] = max(cur['e'], nxt)
        if t[-1] in '.!?…:;"”' or cur['n'] >= 4 or len(cur['text']) >= 240:
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return out


_pipes = {}


def pipe(lang):
    from kokoro import KPipeline

    if lang not in _pipes:
        _pipes[lang] = KPipeline(lang_code=VOICES[lang][0], repo_id='hexgrad/Kokoro-82M')
    return _pipes[lang]


def speak(lang, text, speed):
    chunks = [a for _, _, a in pipe(lang)(text, voice=VOICES[lang][1], speed=speed)]
    chunks = [c.numpy() if hasattr(c, 'numpy') else np.asarray(c) for c in chunks if c is not None]
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


def dub(vid, lang, cues, texts, dur, outdir):
    sents = sentences(cues, texts)
    track = np.zeros(int((dur + 30) * SR), dtype=np.float32)
    cursor = 0.0
    placed = []
    for s in sents:
        slot = max(0.6, s['e'] - s['s'])
        a = speak(lang, s['text'], 1.0)
        need = len(a) / SR
        speed = 1.0
        if need > slot * 1.03:
            speed = min(MAX_SPEED, need / slot * 1.02)
            a = speak(lang, s['text'], speed)
        at = max(s['s'], cursor)
        i0 = int(at * SR)
        if i0 + len(a) > len(track):
            track = np.concatenate([track, np.zeros(i0 + len(a) - len(track) + SR, dtype=np.float32)])
        track[i0 : i0 + len(a)] += a
        cursor = at + len(a) / SR + 0.12
        placed.append([round(at, 2), round(len(a) / SR, 2), round(speed, 2)])
    end = int(min(len(track), max(dur, cursor) * SR + SR))
    wav = os.path.join(outdir, f'{vid}.{lang}.wav')
    sf.write(wav, np.clip(track[:end], -1, 1), SR)
    opus = os.path.join(outdir, f'{vid}.{lang}.opus')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', wav, '-ac', '1', '-c:a', 'libopus', '-b:a', '32k', opus], check=True)
    os.remove(wav)
    late = [p[0] - s['s'] for p, s in zip(placed, sents)]
    return {'sentences': len(sents), 'late_median': round(float(np.median(late)), 2) if late else 0, 'late_max': round(float(max(late)), 2) if late else 0, 'fast': sum(1 for p in placed if p[2] > 1.0), 'placed': placed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lane', type=int, default=1)
    ap.add_argument('--lanes', type=int, default=8)
    ap.add_argument('--budget-min', type=float, default=300)
    ap.add_argument('--ids', default='')
    a = ap.parse_args()
    t0 = time.time()
    outdir = 'out/dub'
    os.makedirs(outdir, exist_ok=True)
    done = set(os.listdir('dub/done')) if os.path.isdir('dub/done') else set()
    if a.ids:
        order = [x for x in a.ids.split(',') if x]
    else:
        cat = get_json('/app/catalogo/')
        week = [l for l in cat['lessons'] if l.get('pa') == cat.get('week')]
        rest = sorted(cat['lessons'], key=lambda l: l.get('p', ''), reverse=True)
        seen = set()
        order = []
        for l in week + rest:
            if l['id'] not in seen:
                seen.add(l['id'])
                order.append(l['id'])
        order = [v for v in order if v not in done and lane_of(v, a.lanes) == a.lane - 1]
    print(f'lane {a.lane}: {len(order)} lessons to dub')
    made = []
    for vid in order:
        if (time.time() - t0) / 60 > a.budget_min:
            break
        t1 = time.time()
        try:
            sub = get_json(f'/legendas/?v={vid}')
        except Exception as err:
            print(f'{vid}: subtitles not readable ({err})')
            continue
        cues = sub['cues']
        dur = cues[-1][1] if cues else 0
        rep = {'id': vid, 'duration': round(dur)}
        for lang in ('pt', 'en'):
            texts = sub.get(lang)
            if not texts:
                continue
            rep[lang] = dub(vid, lang, cues, texts, dur, outdir)
        json.dump(rep, open(os.path.join(outdir, f'{vid}.json'), 'w'))
        made.append(vid)
        el = time.time() - t1
        print(f'{vid}: {dur / 60:.0f} min in {el / 60:.1f} min ({dur / max(el, 1):.1f}× real time) · pt late median {rep.get("pt", {}).get("late_median")}s max {rep.get("pt", {}).get("late_max")}s · faster sentences {rep.get("pt", {}).get("fast")}', flush=True)
        # hand over at once, so a job that dies keeps what it made
        subprocess.run(['bash', 'scripts/dub-handover.sh', vid], check=False)
    print(f'made {len(made)}')


if __name__ == '__main__':
    main()
