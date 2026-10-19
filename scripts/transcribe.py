"""
transcribe.py — Hebrew transcripts for the lessons YouTube never captioned (2026-10-18; 445 videos,
~290 h in the library had "no subtitles"). faster-whisper with ivrit.ai's Hebrew model, on GitHub's CPU
runners; the audio comes from the owner's computer through the draft release stt-queue (YouTube refuses
the runners).

  python scripts/transcribe.py --lane N --lanes L [--budget-min 230] [--ids a,b]

2026-10-19 (the owner: "whisper X is not that good" — in the Torah Readings project Meta's MMS placed
words better than WhisperX, which drifted 5-7 s early): Whisper only WRITES the words; every line's
time then comes from Meta's MMS forced aligner (align.py, torchaudio MMS_FA) over the same audio.

Each lesson becomes the same document the caption harvest writes (videos/transcript/<id>: cues
[start, end, text] of ≤ 6 s / ≤ 90 characters, lang he), so curation, translation, dubbing and the
sites take it like any other. Its audio leaves the queue once the document is written.
"""
import argparse
import glob
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

SUPA = os.environ['SUPABASE_URL'].rstrip('/')
KEY = os.environ['SUPABASE_SERVICE_KEY']
H = {'apikey': KEY, 'authorization': f'Bearer {KEY}'}
MODEL = os.environ.get('STT_MODEL', 'ivrit-ai/whisper-large-v3-turbo-ct2')
REPO = os.environ.get('GITHUB_REPOSITORY', '')


def kv_has(key):
    q = urllib.parse.quote(key, safe='')
    req = urllib.request.Request(f'{SUPA}/rest/v1/global_options?select=key&key=eq.{q}', headers=H)
    return bool(json.load(urllib.request.urlopen(req, timeout=60)))


def kv_put(key, value):
    body = json.dumps([{'key': key, 'value': json.dumps(value, ensure_ascii=False), 'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}]).encode()
    req = urllib.request.Request(
        f'{SUPA}/rest/v1/global_options?on_conflict=key', data=body, method='POST',
        headers={**H, 'content-type': 'application/json', 'prefer': 'resolution=merge-duplicates,return=minimal'},
    )
    urllib.request.urlopen(req, timeout=60)


def lane_of(vid, lanes):
    h = 7
    for ch in vid:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % lanes


def cues_of(segments, max_s=6.0, max_chars=90):
    """words → cues of a few seconds, broken at sentence ends, like the caption harvest's"""
    out = []
    cur = None
    for seg in segments:
        words = seg.words or []
        if not words:
            words = [type('W', (), {'start': seg.start, 'end': seg.end, 'word': seg.text})()]
        for w in words:
            text = (w.word or '').strip()
            if not text:
                continue
            if cur and (w.end - cur[0] > max_s or len(cur[2]) + 1 + len(text) > max_chars or cur[2][-1:] in '.?!'):
                out.append(cur)
                cur = None
            if cur is None:
                cur = [w.start, w.end, text]
            else:
                cur[1] = w.end
                cur[2] += ' ' + text
    if cur:
        out.append(cur)
    clean = []
    for s, e, t in out:
        if clean and s < clean[-1][1]:
            s = clean[-1][1]
        if e <= s:
            e = s + 0.3
        clean.append([round(s, 2), round(e, 2), t])
    return clean


def queue_ids():
    out = subprocess.run(['gh', 'release', 'view', 'stt-queue', '--repo', REPO, '--json', 'assets', '-q', '.assets[].name'], capture_output=True, text=True)
    return [n[:-5] for n in out.stdout.split() if n.endswith('.opus')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lane', type=int, default=1)
    ap.add_argument('--lanes', type=int, default=4)
    ap.add_argument('--budget-min', type=float, default=230)
    ap.add_argument('--ids', default='')
    a = ap.parse_args()
    t0 = time.time()
    ids = [x for x in a.ids.split(',') if x] if a.ids else [v for v in queue_ids() if lane_of(v, a.lanes) == a.lane - 1]
    print(f'lane {a.lane}: {len(ids)} lessons waiting')
    if not ids:
        return
    from faster_whisper import WhisperModel

    model = WhisperModel(MODEL, device='cpu', compute_type='int8', cpu_threads=os.cpu_count() or 4)
    import align as mms  # Meta MMS forced aligner: the times of the lines

    mms.load()
    os.makedirs('audio', exist_ok=True)
    for vid in ids:
        if (time.time() - t0) / 60 > a.budget_min:
            break
        t1 = time.time()
        if kv_has(f'videos/transcript/{vid}'):
            print(f'{vid}: already has a transcript — leaving the queue')
            subprocess.run(['gh', 'release', 'delete-asset', 'stt-queue', f'{vid}.opus', '--repo', REPO, '--yes'])
            continue
        r = subprocess.run(['gh', 'release', 'download', 'stt-queue', '--repo', REPO, '-p', f'{vid}.opus', '-D', 'audio', '--clobber'])
        if r.returncode != 0:
            print(f'{vid}: audio not in the queue')
            continue
        segments, info = model.transcribe(f'audio/{vid}.opus', language='he', beam_size=5, vad_filter=True, word_timestamps=True, condition_on_previous_text=False)
        cues = cues_of(list(segments))
        dur = info.duration
        if len(cues) < 3:
            os.remove(f'audio/{vid}.opus')
            print(f'{vid}: {len(cues)} cues for {dur:.0f}s — no speech?')
            continue
        t2 = time.time()
        aligned = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                wav = mms.audio_of(vid, tmp)  # reads audio/<id>.opus
            new, _groups, _ = mms.align(cues, wav)
            shifts = sorted(n[0] - o[0] for n, o in zip(new, cues))
            aligned = {'by': 'mms_fa', 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'shift': round(shifts[len(shifts) // 2], 2)}
            cues_whisper, cues = cues, new
        except Exception as err:
            print(f'{vid}: MMS alignment failed ({str(err)[:100]}) — keeping Whisper times')
        os.remove(f'audio/{vid}.opus')
        doc = {
            'v': 1, 'videoId': vid, 'lang': 'he', 'duration': round(dur), 'cues': cues, 'title': '', 'summary': '', 'moments': [],
            'model': MODEL.split('/')[-1], 'source': 'whisper:ivrit-ai' + ('+mms' if aligned else ''), 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        if aligned:
            doc['aligned'] = aligned
            doc['cuesOrig'] = cues_whisper
        kv_put(f'videos/transcript/{vid}', doc)
        subprocess.run(['gh', 'release', 'delete-asset', 'stt-queue', f'{vid}.opus', '--repo', REPO, '--yes'])
        el = time.time() - t1
        print(f'{vid}: {dur / 60:.1f} min → {len(cues)} cues in {el / 60:.1f} min ({dur / max(el, 1):.1f}× real time; MMS {time.time() - t2:.0f}s{', shift ' + format(aligned['shift'], '+.2f') + 's' if aligned else ''})', flush=True)


if __name__ == '__main__':
    main()
