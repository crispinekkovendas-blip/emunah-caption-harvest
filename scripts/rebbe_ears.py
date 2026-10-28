"""The Rebbe model, dataset step 3: the recordings in 30-minute chunks for the ears (rebbe-ears.yml).

2026-10-28 (the owner: "Go ahead, let's train this"). The published texts are edited, not what the Rebbe said
(rebbe_verify.py kept ~1 minute per talk), so the training text is made from the recordings: Demucs, then three
ears (WhisperX German, WhisperX Hebrew/ivrit.ai, Meta MMS), then Claude curates (rebbe_curate.py). Every chunk
keeps its original audio (clip-raw.opus) for training.

    python scripts/rebbe_ears.py plan [--only REGEX | --only pilot] [--max N]   → chunks=[…] to GITHUB_OUTPUT
    python scripts/rebbe_ears.py fetch --url U --start S --len L --id ID --out out/ears
"""
import argparse
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

SR = 16000
CHUNK = 1800
ITEMS = ['rebbe-chabad']
# 10_Yud_Alef_Nissan_5743 is the English translation's sound; the niggun has no speech
SKIP = re.compile(r'English_Sound|niggun|\.ia\.', re.I)
# the pilot: the talk of the four-ears test and of video-batches/stt-test/rebbe/curated-sample.md
PILOT = re.compile(r'^10_Leil_Yud_Gimmel_Nissan_5751')


def slug(name):
    s = re.sub(r'\.(mp4|mp3|webm|ogg|m4a|mkv)$', '', name, flags=re.I)
    return re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()[:60]


def recordings():
    seen, out = set(), []
    for item in ITEMS:
        meta = json.load(urllib.request.urlopen(f'https://archive.org/metadata/{urllib.parse.quote(item)}', timeout=60))
        for f in meta.get('files', []):
            name = f.get('name', '')
            if not name.lower().endswith(('.mp4', '.mp3', '.webm', '.ogg', '.m4a', '.mkv')) or SKIP.search(name):
                continue
            try:
                length = float(f.get('length') or 0)
            except ValueError:
                length = 0
            key = (round(length), f.get('size'))
            if not length or key in seen:  # the same recording under a second name
                continue
            seen.add(key)
            out.append({'item': item, 'file': name, 'length': length,
                        'url': f'https://archive.org/download/{urllib.parse.quote(item)}/{urllib.parse.quote(name)}'})
    return sorted(out, key=lambda r: r['file'])


def plan(a):
    chunks = []
    recs = recordings()
    for r in recs:
        if a.only == 'pilot' and not PILOT.search(r['file']):
            continue
        if a.only not in ('', 'pilot') and not re.search(a.only, r['file'], re.I):
            continue
        n = max(1, round(r['length'] / CHUNK))  # a last piece under 15 min joins the one before
        for i in range(n):
            start = i * CHUNK
            length = r['length'] - start if i == n - 1 else CHUNK
            chunks.append({'id': f'{slug(r["file"])}-{i:02d}', 'file': r['file'], 'url': r['url'],
                           'start': start, 'len': round(length)})
    if a.only == 'pilot':
        chunks = chunks[:1]
    if a.max:
        chunks = chunks[: a.max]
    hours = sum(c['len'] for c in chunks) / 3600
    print(f'{len(recs)} recordings; {len(chunks)} chunks, {hours:.1f} h')
    for c in chunks:
        print(f'  {c["id"]}  {c["start"] // 60:.0f}–{(c["start"] + c["len"]) // 60:.0f} min')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'chunks={json.dumps(chunks)}\n')


def fetch(a):
    os.makedirs(a.out, exist_ok=True)
    clip = os.path.join(a.out, 'clip.opus')
    # ffmpeg reads only the range it needs from archive.org (HTTP range requests)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(a.start), '-t', str(a.len), '-i', a.url, '-vn',
                    '-ac', '1', '-ar', str(SR), '-c:a', 'libopus', '-b:a', '32k', clip], check=True)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', clip],
                               capture_output=True, text=True).stdout.strip() or 0)
    src = {'id': a.id, 'source': 'archive.org', 'url': a.url, 'clip_offset_s': a.start, 'clip_minutes': round(dur / 60, 2)}
    json.dump(src, open(os.path.join(a.out, 'source.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(json.dumps(src, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['plan', 'fetch'])
    ap.add_argument('--only', default='')
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--url', default='')
    ap.add_argument('--start', type=float, default=0)
    ap.add_argument('--len', type=float, default=CHUNK)
    ap.add_argument('--id', default='')
    ap.add_argument('--out', default='out/ears')
    a = ap.parse_args()
    {'plan': plan, 'fetch': fetch}[a.step](a)


if __name__ == '__main__':
    main()
