"""
transcribe.py — Hebrew transcripts for the lessons YouTube never captioned (2026-10-18; 445 videos,
~290 h in the library had "no subtitles"). faster-whisper with ivrit.ai's Hebrew model, on GitHub's CPU
runners; the audio comes from the owner's computer through the draft release stt-queue (YouTube refuses
the runners).

  python scripts/transcribe.py --lane N --lanes L [--budget-min 230] [--ids a,b] [--lang he|yi] [--out DIR]

2026-10-24 (the owner: "try to transcribe the Lubavitcher Rebbe's shiurim, with one"): --lang yi for the
Rebbe's sichos, which are in Yiddish. ivrit.ai's model knows only Hebrew and writes Yiddish as invented
Hebrew, so Yiddish takes OpenAI's large-v3 (Yiddish is one of its languages) with the same Hebrew-script
aligner; its audio waits in its own draft release stt-queue-yi, so the hourly Hebrew lanes never take it.
The document says lang yi — the Hebrew translation batches (batch-make: lang he only) leave it alone.

2026-10-19, after a test on 12 min of Rav Meir Eliyahu (compare_stt.py, run 39248751695): WhisperX with
ivrit.ai's model ("B") wrote the Hebrew best (12.9 % apart from YouTube's automatic captions, and right
twice as often where they disagree) and timed it best (half the words within 0.18 s; Meta MMS 0.24-0.26 s).
So: WhisperX (ivrit.ai Whisper → WhisperX's Hebrew wav2vec2 word alignment) → cues.

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
REPO = os.environ.get('GITHUB_REPOSITORY', '')
# language → (Whisper model, source tag); the aligner is the Hebrew one for both (same alphabet: a Yiddish
# letter it does not know — װ ײ ױ, pointed alefs — leaves that word with its neighbours' time)
LANGS = {
    'he': ('ivrit-ai/whisper-large-v3-turbo-ct2', 'whisperx:ivrit-ai'),
    'yi': ('large-v3', 'whisperx:large-v3'),
}


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


def load_wav(path):
    import numpy as np

    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype('float32') / 32768.0


def segments_of(segs):
    """WhisperX's aligned segments → objects with .words (start/end/word) for cues_of; a word the
    aligner could not place takes its neighbours' time"""
    out = []
    for sg in segs:
        o = type('S', (), {})()
        o.start, o.end, o.text = sg['start'], sg['end'], sg.get('text', '')
        o.words = []
        last = sg['start']
        for w in sg.get('words', []):
            x = type('W', (), {})()
            x.start = w.get('start', last)
            x.end = w.get('end', x.start)
            x.word = w.get('word', '')
            last = x.end
            o.words.append(x)
        out.append(o)
    return out


def queue_ids(queue):
    out = subprocess.run(['gh', 'release', 'view', queue, '--repo', REPO, '--json', 'assets', '-q', '.assets[].name'], capture_output=True, text=True)
    return [n[:-5] for n in out.stdout.split() if n.endswith('.opus')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lane', type=int, default=1)
    ap.add_argument('--lanes', type=int, default=4)
    ap.add_argument('--budget-min', type=float, default=230)
    ap.add_argument('--ids', default='')
    ap.add_argument('--lang', default='he', choices=sorted(LANGS))
    ap.add_argument('--out', default='', help='also write each document here as <id>.json')
    ap.add_argument('--owners', type=int, default=0, help='only print the lanes (1..N) that own audio in the queue')
    # 2026-10-25: the Emunah Shlemah site's own pipeline (emunah-shlemah-site meir-new.yml) downloads the audio on
    # its runner and hands it here — no queue release involved
    ap.add_argument('--audio-dir', default='', help='take <id>.opus from this folder instead of the queue release')
    a = ap.parse_args()
    model_name, source = LANGS[a.lang]
    model_name = os.environ.get('STT_MODEL') or model_name
    queue = 'stt-queue' if a.lang == 'he' else f'stt-queue-{a.lang}'
    # 2026-10-24: a lane restarted itself whenever ANY file was in the queue — 13 of 14 lanes spun every 3½ min
    # with "0 lessons waiting" (17,000+ runs) and held the job slots the dub and translation runs wait for. The
    # kick now wakes only the lanes that own files, and a lane goes on only while it owns files and made progress.
    if a.owners:
        print(' '.join(str(n) for n in sorted({lane_of(v, a.owners) + 1 for v in queue_ids(queue)})))
        return
    t0 = time.time()
    ids = [x for x in a.ids.split(',') if x] if a.ids else [v for v in queue_ids(queue) if lane_of(v, a.lanes) == a.lane - 1]
    print(f'lane {a.lane}: {len(ids)} lessons waiting')
    done = 0

    def report():
        left = 0 if a.ids else sum(1 for v in queue_ids(queue) if lane_of(v, a.lanes) == a.lane - 1)
        print(f'lane {a.lane}: {done} transcribed, {left} left')
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f'done={done}\nleft={left}\n')

    if not ids:
        report()
        return
    import whisperx

    try:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language=a.lang, vad_method='silero')
    except TypeError:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language=a.lang)
    am, meta = whisperx.load_align_model(language_code='he', device='cpu')
    os.makedirs('audio', exist_ok=True)
    for vid in ids:
        if (time.time() - t0) / 60 > a.budget_min:
            break
        t1 = time.time()
        if kv_has(f'videos/transcript/{vid}'):
            print(f'{vid}: already has a transcript — leaving the queue')
            if not a.audio_dir:
                subprocess.run(['gh', 'release', 'delete-asset', queue, f'{vid}.opus', '--repo', REPO, '--yes'])
            continue
        if a.audio_dir:
            src = os.path.join(a.audio_dir, f'{vid}.opus')
            if not os.path.exists(src):
                print(f'{vid}: no audio in {a.audio_dir}')
                continue
        else:
            r = subprocess.run(['gh', 'release', 'download', queue, '--repo', REPO, '-p', f'{vid}.opus', '-D', 'audio', '--clobber'])
            if r.returncode != 0:
                print(f'{vid}: audio not in the queue')
                continue
            src = f'audio/{vid}.opus'
        wav = load_wav(src)
        if not a.audio_dir:
            os.remove(src)
        dur = len(wav) / 16000
        res = model.transcribe(wav, batch_size=8, language=a.lang)
        al = whisperx.align(res['segments'], am, meta, wav, 'cpu', return_char_alignments=False)
        cues = cues_of(segments_of(al['segments']))
        if len(cues) < 3:
            # no speech: out of the queue, or the lane would take it again forever
            print(f'{vid}: {len(cues)} cues for {dur:.0f}s — no speech? removed from the queue')
            if not a.audio_dir:
                subprocess.run(['gh', 'release', 'delete-asset', queue, f'{vid}.opus', '--repo', REPO, '--yes'])
            continue
        doc = {
            'v': 1, 'videoId': vid, 'lang': a.lang, 'duration': round(dur), 'cues': cues, 'title': '', 'summary': '', 'moments': [],
            'model': model_name.split('/')[-1], 'source': source, 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        kv_put(f'videos/transcript/{vid}', doc)
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            with open(os.path.join(a.out, f'{vid}.json'), 'w', encoding='utf8') as f:
                json.dump(doc, f, ensure_ascii=False, indent=0)
        if not a.audio_dir:
            subprocess.run(['gh', 'release', 'delete-asset', queue, f'{vid}.opus', '--repo', REPO, '--yes'])
        done += 1
        el = time.time() - t1
        print(f'{vid}: {dur / 60:.1f} min → {len(cues)} cues in {el / 60:.1f} min ({dur / max(el, 1):.1f}× real time)', flush=True)
    report()


if __name__ == '__main__':
    main()
