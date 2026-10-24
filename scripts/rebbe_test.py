"""
rebbe_test.py — one test of the transcription method on the Lubavitcher Rebbe (2026-10-24, the owner: "try to
transcribe Lubavitcher Rebbe shiurim, try with one, using the same method … run the test within github
servers").

The method of the library (see transcribe.py, align.py, compare_stt.py): WhisperX writes the words and
places them with its Hebrew-script aligner; Meta MMS (align.py) then retimes every line against the audio.
The Rebbe spoke Yiddish, which ivrit.ai's Hebrew model does not know, so the words come from large-v3
(transcribe.py --lang yi) — variant A of the 2026-10-19 comparison — and MMS reads the letters as Yiddish.

YouTube refuses GitHub's runners, so the audio comes from archive.org (or --url, a direct audio link).
Nothing is written to Supabase: the result is a JSON and a readable text, committed to
video-batches/stt-test/rebbe/.

  python scripts/rebbe_test.py fetch  [--url URL] [--item IA_ID] [--minutes 20] [--offset 60] --out out/rebbe
  python scripts/rebbe_test.py stt    --out out/rebbe          (WhisperX large-v3, Yiddish)
  python scripts/rebbe_test.py retime --out out/rebbe          (Meta MMS, Yiddish romanization)
"""
import argparse
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

SR = 16000
UA = {'user-agent': 'emunah-caption-harvest (rebbe test)'}
# the first run's single query found 2 items and took Rabbi Leibel Groner's farbrengen: search by creator and
# title too, and score — the Rebbe himself as the creator first, other rabbis' talks last
QUERIES = [
    'creator:(Schneerson OR "Lubavitcher Rebbe" OR "Menachem Mendel") AND mediatype:audio',
    'title:("Lubavitcher Rebbe" OR "the Rebbe" OR Schneerson) AND title:(sicha OR sichos OR sichot OR farbrengen OR maamar OR sichah) AND mediatype:audio',
    '(sicha OR sichos OR farbrengen OR maamar) AND (Schneerson OR "Lubavitcher Rebbe") AND mediatype:audio',
]
REBBE = re.compile(r'schneerson|lubavitcher rebbe|menachem mendel|\brebbe\b', re.I)
TALK = re.compile(r'sich|farbreng|maamar|ma\'amar|yechidus|dollars', re.I)
OTHER = re.compile(r'\brabbi\b|\brav\b|\br\.\s|groner|shiur by|class by|lecture by|niggun|nigun|song|music', re.I)


def score(d):
    title = d.get('title') or ''
    creator = d.get('creator') or ''
    creator = ' '.join(creator) if isinstance(creator, list) else creator
    s = 0
    if re.search(r'schneerson|lubavitcher rebbe|menachem mendel', creator, re.I):
        s += 4
    if REBBE.search(title):
        s += 2
    if TALK.search(title):
        s += 2
    if OTHER.search(title) or (OTHER.search(creator) and not REBBE.search(creator)):
        s -= 6
    return s


def get_json(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))


def seconds(length):
    """archive.org's file length: '1234.5' or 'mm:ss' or 'hh:mm:ss'"""
    if not length:
        return 0
    if ':' in str(length):
        s = 0
        for p in str(length).split(':'):
            s = s * 60 + float(p)
        return s
    try:
        return float(length)
    except ValueError:
        return 0


def pick_archive(item, min_s):
    """the first archive.org recording of the Rebbe long enough for the clip"""
    if item:
        ids = [item]
    else:
        seen = {}
        for query in QUERIES:
            q = urllib.parse.urlencode({'q': query, 'fl[]': ['identifier', 'title', 'creator', 'downloads'], 'rows': 50, 'sort[]': 'downloads desc', 'output': 'json'}, doseq=True)
            for d in get_json(f'https://archive.org/advancedsearch.php?{q}')['response']['docs']:
                seen.setdefault(d['identifier'], d)
        docs = sorted(seen.values(), key=lambda d: (-score(d), -(d.get('downloads') or 0)))
        print(f'archive.org: {len(docs)} candidates (score, downloads, id, creator, title)')
        for d in docs[:25]:
            print(f'  {score(d):3d} {d.get("downloads") or 0:7d}  {d["identifier"]}  [{d.get("creator", "")}]  {d.get("title", "")}')
        ids = [d['identifier'] for d in docs if score(d) > 0]
    for ident in ids:
        meta = get_json(f'https://archive.org/metadata/{urllib.parse.quote(ident)}')
        files = [f for f in meta.get('files', []) if f.get('name', '').lower().endswith(('.mp3', '.ogg', '.m4a', '.opus', '.wav', '.flac'))]
        files = [f for f in files if seconds(f.get('length')) >= min_s] or []
        if not files:
            continue
        files.sort(key=lambda f: (not f['name'].lower().endswith('.mp3'), seconds(f.get('length'))))
        f = files[0]
        md = meta.get('metadata', {})
        return {
            'source': 'archive.org',
            'item': ident,
            'title': md.get('title', ''),
            'date': md.get('date', ''),
            'file': f['name'],
            'length_s': round(seconds(f.get('length'))),
            'url': f'https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(f["name"])}',
            'page': f'https://archive.org/details/{ident}',
        }
    raise SystemExit('no archive.org recording long enough')


def fetch(a):
    os.makedirs(a.out, exist_ok=True)
    need = a.offset + a.minutes * 60
    raw = os.path.join(a.out, 'source.bin')
    if a.url and re.search(r'youtu\.?be', a.url):
        src = {'source': 'youtube', 'url': a.url}
        r = subprocess.run(['python', '-m', 'yt_dlp', '-q', '--no-warnings', '-f', 'bestaudio', '-o', raw, a.url])
        if r.returncode != 0:
            raise SystemExit('YouTube refused the runner — use archive.org (no --url) or a direct audio link')
    else:
        src = {'source': 'url', 'url': a.url} if a.url else pick_archive(a.item, need)
        print(f'audio: {src["url"]}')
        req = urllib.request.Request(src['url'], headers=UA)
        with urllib.request.urlopen(req, timeout=600) as r, open(raw, 'wb') as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    clip = os.path.join(a.out, 'clip.opus')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(a.offset), '-t', str(a.minutes * 60), '-i', raw,
                    '-ac', '1', '-ar', str(SR), '-c:a', 'libopus', '-b:a', '32k', clip], check=True)
    os.remove(raw)
    src.update({'clip_offset_s': a.offset, 'clip_minutes': a.minutes})
    json.dump(src, open(os.path.join(a.out, 'source.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(json.dumps(src, ensure_ascii=False, indent=1))


def stt(a):
    os.environ.setdefault('SUPABASE_URL', 'http://unused')
    os.environ.setdefault('SUPABASE_SERVICE_KEY', 'unused')
    import whisperx
    from transcribe import LANGS, cues_of, load_wav, segments_of

    model_name, _ = LANGS['yi']
    wav = load_wav(os.path.join(a.out, 'clip.opus'))
    dur = len(wav) / SR
    t = time.time()
    try:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language='yi', vad_method='silero')
    except TypeError:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language='yi')
    res = model.transcribe(wav, batch_size=8, language='yi')
    t_asr = time.time() - t
    am, meta = whisperx.load_align_model(language_code='he', device='cpu')
    t = time.time()
    al = whisperx.align(res['segments'], am, meta, wav, 'cpu', return_char_alignments=False)
    t_al = time.time() - t
    cues = cues_of(segments_of(al['segments']))
    placed = sum(1 for sg in al['segments'] for w in sg.get('words', []) if 'start' in w)
    total = sum(len(sg.get('words', [])) for sg in al['segments'])
    doc = {
        'lang': 'yi', 'model': model_name, 'aligner': 'whisperx wav2vec2-hebrew', 'duration': round(dur),
        'asr_s': round(t_asr), 'align_s': round(t_al), 'words': total, 'words_placed': placed, 'cues': cues,
    }
    json.dump(doc, open(os.path.join(a.out, 'stt.json'), 'w', encoding='utf8'), ensure_ascii=False)
    print(f'{dur / 60:.1f} min → {len(cues)} cues, {placed}/{total} words placed by the aligner; ASR {t_asr:.0f}s, align {t_al:.0f}s')
    for c in cues[:25]:
        print(f'  {c[0]:7.2f} {c[1]:7.2f}  {c[2]}')


def retime(a):
    os.environ.setdefault('SUPABASE_URL', 'http://unused')
    os.environ.setdefault('SUPABASE_SERVICE_KEY', 'unused')
    import statistics

    import align as al
    from transcribe import load_wav

    doc = json.load(open(os.path.join(a.out, 'stt.json'), encoding='utf8'))
    src = json.load(open(os.path.join(a.out, 'source.json'), encoding='utf8'))
    wav = load_wav(os.path.join(a.out, 'clip.opus'))
    al.load()
    al.LCODE = 'yid'
    t = time.time()
    new, groups, dur = al.align(doc['cues'], wav)
    t_mms = time.time() - t
    d = [n[0] - o[0] for n, o in zip(new, doc['cues'])]
    errors = sum(1 for g in groups if 'error' in g)
    result = {
        **{k: v for k, v in doc.items() if k != 'cues'},
        'source': src,
        'mms_s': round(t_mms),
        'mms_shift_median': round(statistics.median(d), 2) if d else 0,
        'mms_shift_abs_median': round(statistics.median([abs(x) for x in d]), 2) if d else 0,
        'mms_groups_failed': f'{errors}/{len(groups)}',
        'cues_whisperx': doc['cues'],
        'cues': new,
    }
    name = (src.get('item') or 'url').replace('/', '_')
    out_dir = 'video-batches/stt-test/rebbe'
    os.makedirs(out_dir, exist_ok=True)
    json.dump(result, open(os.path.join(out_dir, f'{name}.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    clock = lambda s: f'{int(s // 60):02d}:{s % 60:05.2f}'
    with open(os.path.join(out_dir, f'{name}.txt'), 'w', encoding='utf8') as f:
        f.write(f'{src.get("title", "")}\n{src.get("page") or src.get("url")}\n')
        f.write(f'clip: from {src["clip_offset_s"]} s, {src["clip_minutes"]} min · words: {doc["model"]} (yi) · times: Meta MMS (yid)\n')
        f.write(f'MMS moved the lines by {result["mms_shift_abs_median"]} s (median); failed groups {result["mms_groups_failed"]}\n\n')
        for c in new:
            f.write(f'{clock(c[0])}  {c[2]}\n')
    print(f'MMS: {t_mms:.0f}s, median shift {result["mms_shift_median"]} s (|{result["mms_shift_abs_median"]}|), failed groups {errors}/{len(groups)}')
    print(f'wrote {out_dir}/{name}.json and .txt')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['fetch', 'stt', 'retime'])
    ap.add_argument('--url', default='')
    ap.add_argument('--item', default='')
    ap.add_argument('--minutes', type=float, default=20)
    ap.add_argument('--offset', type=float, default=60)
    ap.add_argument('--out', default='out/rebbe')
    a = ap.parse_args()
    {'fetch': fetch, 'stt': stt, 'retime': retime}[a.step](a)


if __name__ == '__main__':
    main()
