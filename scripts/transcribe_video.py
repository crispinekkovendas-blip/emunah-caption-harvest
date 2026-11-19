"""
transcribe_video.py - a transcript of any one video (2026-11-19; the owner: "make github run a script to
transcribe I think its WhisperX, transcribe this video"). Outside the lessons pipeline: nothing is read
from or written to the library. The workflow (transcribe-video.yml) downloads the audio into a folder,
WhisperX writes the words and times them, and the transcript leaves as the run's artifact:

  <id>.txt   to read - a header, then paragraphs that each start with their [mm:ss]
  <id>.srt   subtitles (cues of <= 6 s / <= 84 characters)
  <id>.json  every sentence with its words and their times

  python scripts/transcribe_video.py --dir dl --out out [--lang en] [--model large-v3-turbo]

The WhisperX calls are the ones transcribe.py already runs on these CPU runners (int8, silero VAD,
batch 8). A language WhisperX has no aligner for keeps Whisper's own segment times.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import time


def load_wav(path):
    import numpy as np

    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype('float32') / 32768.0


def plain(segments):
    """WhisperX's segments -> plain numbers and strings; a word the aligner could not place (a number,
    a symbol) takes its neighbours' time"""
    out = []
    for sg in segments:
        text = (sg.get('text') or '').strip()
        if not text:
            continue
        words = []
        last = float(sg['start'])
        for w in sg.get('words') or []:
            word = (w.get('word') or '').strip()
            if not word:
                continue
            s = float(w.get('start', last))
            e = float(w.get('end', s))
            last = e
            words.append({'word': word, 'start': round(s, 2), 'end': round(e, 2)})
        out.append({'start': round(float(sg['start']), 2), 'end': round(float(sg['end']), 2), 'text': text, 'words': words})
    return out


def cues_of(segments, max_s=6.0, max_chars=84):
    """words -> subtitle cues of a few seconds, broken at sentence ends"""
    out = []
    cur = None
    for sg in segments:
        words = sg['words'] or [{'word': sg['text'], 'start': sg['start'], 'end': sg['end']}]
        for w in words:
            if cur and (w['end'] - cur[0] > max_s or len(cur[2]) + 1 + len(w['word']) > max_chars or cur[2][-1:] in '.?!'):
                out.append(cur)
                cur = None
            if cur is None:
                cur = [w['start'], w['end'], w['word']]
            else:
                cur[1] = w['end']
                cur[2] += ' ' + w['word']
    if cur:
        out.append(cur)
    clean = []
    for s, e, t in out:
        if clean and s < clean[-1][1]:
            s = clean[-1][1]
        if e <= s:
            e = s + 0.3
        clean.append([s, e, t])
    return clean


def paragraphs_of(segments, gap=1.5, min_chars=200, max_chars=900):
    """sentences -> paragraphs to read: a new one after a pause, or when it has grown long"""
    out = []
    cur = None
    last_end = 0.0
    for sg in segments:
        if cur and ((sg['start'] - last_end > gap and len(cur[1]) >= min_chars) or len(cur[1]) + 1 + len(sg['text']) > max_chars):
            out.append(cur)
            cur = None
        if cur is None:
            cur = [sg['start'], sg['text']]
        else:
            cur[1] += ' ' + sg['text']
        last_end = sg['end']
    if cur:
        out.append(cur)
    return out


def clock(t):
    h, r = divmod(int(t), 3600)
    m, s = divmod(r, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='dl', help='the folder the workflow downloaded into (audio + .info.json)')
    ap.add_argument('--out', default='out')
    ap.add_argument('--lang', default='', help='spoken language code; empty = Whisper detects it')
    ap.add_argument('--model', default='large-v3-turbo')
    a = ap.parse_args()
    lang = a.lang.strip().lower() or None
    model_name = a.model.strip() or 'large-v3-turbo'

    info = {}
    for p in glob.glob(os.path.join(a.dir, '*.info.json')):
        with open(p, encoding='utf8') as f:
            info = json.load(f)
    media = sorted((p for p in glob.glob(os.path.join(a.dir, '*')) if os.path.isfile(p) and not p.endswith(('.json', '.part', '.ytdl'))), key=os.path.getsize)
    if not media:
        raise SystemExit(f'no audio in {a.dir}')
    src = media[-1]
    vid = re.sub(r'[^A-Za-z0-9_-]', '_', str(info.get('id') or os.path.splitext(os.path.basename(src))[0]))
    wav = load_wav(src)
    dur = len(wav) / 16000
    print(f'{vid}: {dur / 60:.1f} min of audio, model {model_name}, language {lang or "to be detected"}', flush=True)

    import whisperx

    t0 = time.time()
    try:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language=lang, vad_method='silero')
    except TypeError:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language=lang)
    try:
        res = model.transcribe(wav, batch_size=8, language=lang, print_progress=True)
    except TypeError:
        res = model.transcribe(wav, batch_size=8, language=lang)
    lang = res.get('language') or lang or ''
    segments = res['segments']
    t1 = time.time()
    print(f'words written in {(t1 - t0) / 60:.1f} min ({dur / max(t1 - t0, 1):.1f}x real time), language {lang}', flush=True)

    aligned = False
    try:
        am, meta = whisperx.load_align_model(language_code=lang, device='cpu')
        segments = whisperx.align(segments, am, meta, wav, 'cpu', return_char_alignments=False)['segments']
        aligned = True
        print(f'words timed in {(time.time() - t1) / 60:.1f} min', flush=True)
    except Exception as e:  # no aligner for this language, or it could not be fetched
        print(f'no word times for "{lang}" ({type(e).__name__}: {e}) - the segments keep Whisper\'s own times', flush=True)

    segments = plain(segments)
    n_words = sum(len(sg['text'].split()) for sg in segments)
    if n_words < 5:
        raise SystemExit(f'{vid}: {n_words} words for {dur:.0f} s of audio - no speech?')

    title = info.get('title') or vid
    channel = info.get('channel') or info.get('uploader') or ''
    url = info.get('webpage_url') or ''
    day = info.get('upload_date') or ''
    if len(day) == 8:
        day = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    generated = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    os.makedirs(a.out, exist_ok=True)

    head = [title, ' | '.join(x for x in (channel, day, clock(dur)) if x)]
    if url:
        head.append(url)
    head.append(f'Transcript: WhisperX ({model_name.split("/")[-1]}), language {lang}, {generated[:10]}')
    with open(os.path.join(a.out, f'{vid}.txt'), 'w', encoding='utf8', newline='\n') as f:
        f.write('\n'.join(head) + '\n')
        for start, text in paragraphs_of(segments):
            f.write(f'\n[{clock(start)}] {text}\n')

    with open(os.path.join(a.out, f'{vid}.srt'), 'w', encoding='utf8', newline='\n') as f:
        for i, (s, e, t) in enumerate(cues_of(segments), 1):
            f.write(f'{i}\n{srt_time(s)} --> {srt_time(e)}\n{t}\n\n')

    doc = {
        'id': vid, 'title': title, 'channel': channel, 'url': url, 'uploaded': day, 'duration': round(dur), 'lang': lang,
        'model': model_name.split('/')[-1], 'source': 'whisperx', 'wordTimes': aligned, 'generated': generated, 'segments': segments,
    }
    with open(os.path.join(a.out, f'{vid}.json'), 'w', encoding='utf8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False)

    el = time.time() - t0
    line = f'{vid}: {dur / 60:.1f} min -> {n_words} words, {len(segments)} sentences in {el / 60:.1f} min ({dur / max(el, 1):.1f}x real time)'
    print(line, flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf8') as f:
            f.write(f'**{title}**\n\n{line}\n\nThe transcript is the artifact `transcript` of this run (txt, srt, json).\n')


if __name__ == '__main__':
    main()
