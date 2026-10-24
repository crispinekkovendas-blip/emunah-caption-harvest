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
  python scripts/rebbe_test.py stt --lang de|he --anti-loop    (the "two ears" passes, WhisperX, 2026-10-24)
  python scripts/rebbe_test.py merge  --out out/rebbe          (German lines + the Hebrew words heard with them)
  python scripts/rebbe_test.py clean | mms | stt --lang en --prompt   (four ears: Demucs, Meta MMS Yiddish,
                                                               WhisperX translate, the vocabulary prompt)
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
LIST_ONLY = False
UA = {'user-agent': 'emunah-caption-harvest (rebbe test)'}
# the first run's single query found 2 items and took Rabbi Leibel Groner's farbrengen: search by creator and
# title too, and score — the Rebbe himself as the creator first, other rabbis' talks last
# (the second found 5, none of them the Rebbe: archive.org also spells him Schneersohn / Shneerson and keeps
# many of his talks as video — the audio is taken from those too)
MEDIA = 'mediatype:(audio OR movies)'
WHO = '(Schneerson OR Schneersohn OR Shneerson OR Shneersohn OR "Lubavitcher Rebbe" OR "Menachem Mendel" OR "Lubavitch Rebbe")'
QUERIES = [
    f'creator:{WHO} AND {MEDIA}',
    f'title:{WHO} AND {MEDIA}',
    f'subject:{WHO} AND {MEDIA}',
    f'(Rebbe OR Lubavitch OR Chabad) AND (sicha OR sichos OR sichot OR farbrengen OR maamar OR "ma\'amar") AND {MEDIA}',
]
REBBE = re.compile(r'schneers|shneers|lubavitcher rebbe|lubavitch rebbe|menachem mendel|\brebbe\b', re.I)
TALK = re.compile(r'sich|farbreng|maamar|ma\'amar|yechidus|dollars', re.I)
OTHER = re.compile(r'\brabbi\b|\brav\b|\br\.\s|groner|shiur by|class by|lecture by|niggun|nigun|song|music', re.I)


def score(d):
    title = d.get('title') or ''
    creator = d.get('creator') or ''
    creator = ' '.join(creator) if isinstance(creator, list) else creator
    s = 0
    if re.search(r'schneers|shneers|lubavitcher rebbe|lubavitch rebbe|menachem mendel', creator, re.I):
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
    """the first archive.org recording of the Rebbe long enough for the clip (a named item: any length — the
    Rebbe's JEM clips are a few minutes long, and the run before skipped them for a Drupal talk by a Guy Schneerson)"""
    if item:
        min_s = 60
        ids = [item]
    else:
        seen = {}
        for query in QUERIES:
            q = urllib.parse.urlencode({'q': query, 'fl[]': ['identifier', 'title', 'creator', 'downloads', 'mediatype'], 'rows': 100, 'sort[]': 'downloads desc', 'output': 'json'}, doseq=True)
            for d in get_json(f'https://archive.org/advancedsearch.php?{q}')['response']['docs']:
                seen.setdefault(d['identifier'], d)
        docs = sorted(seen.values(), key=lambda d: (-score(d), -(d.get('downloads') or 0)))
        print(f'archive.org: {len(docs)} candidates (score, downloads, id, creator, title)')
        for d in docs[:60]:
            print(f'  {score(d):3d} {d.get("downloads") or 0:7d} {d.get("mediatype", "")[:5]:5}  {d["identifier"]}  [{d.get("creator", "")}]  {d.get("title", "")}')
        if LIST_ONLY:
            raise SystemExit(0)
        ids = [d['identifier'] for d in docs if score(d) > 0]
    for ident in ids:
        meta = get_json(f'https://archive.org/metadata/{urllib.parse.quote(ident)}')
        files = [f for f in meta.get('files', []) if f.get('name', '').lower().endswith(('.mp3', '.ogg', '.m4a', '.opus', '.wav', '.flac', '.mp4', '.webm', '.mkv'))]
        if item:
            print(f'{ident}: ' + ', '.join(f'{f["name"]} ({f.get("length", "?")} s, {f.get("size", "?")} B)' for f in files))
        # a file archive.org gives no length for is measured after the download (ffprobe)
        files = [f for f in files if not f.get('length') or seconds(f.get('length')) >= min_s]
        if not files:
            continue
        # audio before video, then the smallest file (a video's audio is the same, its download is not)
        files.sort(key=lambda f: (f['name'].lower().endswith(('.mp4', '.webm', '.mkv')), int(f.get('size') or 0)))
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


MEDIA_EXT = ('.mp3', '.ogg', '.m4a', '.opus', '.wav', '.flac', '.mp4', '.webm', '.mkv')


def fetch_many(a, items):
    """several short recordings of the Rebbe joined into one clip (run 5: JEM's clip alone is 57 s)"""
    tmp = os.path.join(a.out, 'parts')
    os.makedirs(tmp, exist_ok=True)
    parts, total = [], 0.0
    for ident in items:
        if total >= a.minutes * 60:
            break
        meta = get_json(f'https://archive.org/metadata/{urllib.parse.quote(ident)}')
        title = meta.get('metadata', {}).get('title', '')
        by_stem = {}
        for f in meta.get('files', []):
            n = f.get('name', '')
            if n.lower().endswith(MEDIA_EXT):
                by_stem.setdefault(os.path.splitext(n)[0], []).append(f)
        print(f'{ident} ({title}): {len(by_stem)} recordings')
        for stem, fs in sorted(by_stem.items()):
            if total >= a.minutes * 60:
                break
            f = min(fs, key=lambda f: int(f.get('size') or 1 << 40))  # one format per recording, the smallest
            url = f'https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(f["name"])}'
            raw = os.path.join(tmp, 'raw.bin')
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(raw, 'wb') as out:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    out.write(b)
            wav = os.path.join(tmp, f'{len(parts):03d}.wav')
            if subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', raw, '-vn', '-ac', '1', '-ar', str(SR), wav]).returncode != 0:
                print(f'  {f["name"]}: no audio')
                continue
            dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', wav],
                                       capture_output=True, text=True).stdout.strip() or 0)
            parts.append({'item': ident, 'title': title, 'file': f['name'], 'start_s': round(total, 2), 'length_s': round(dur, 2), 'url': url})
            total += dur
            print(f'  {f["name"]}: {dur:.0f} s')
    if not parts:
        raise SystemExit('no audio in these items')
    lst = os.path.join(tmp, 'list.txt')
    with open(lst, 'w') as f:
        for i in range(len(parts)):
            f.write(f"file '{i:03d}.wav'\n")
    clip = os.path.join(a.out, 'clip.opus')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-t', str(a.minutes * 60),
                    '-ac', '1', '-ar', str(SR), '-c:a', 'libopus', '-b:a', '32k', clip], check=True)
    subprocess.run(['rm', '-rf', tmp])
    src = {'source': 'archive.org', 'item': 'rebbe-clips', 'title': 'The Lubavitcher Rebbe — ' + ' · '.join(dict.fromkeys(p['title'] for p in parts)),
           'parts': parts, 'clip_offset_s': 0, 'clip_minutes': round(min(total, a.minutes * 60) / 60, 2)}
    json.dump(src, open(os.path.join(a.out, 'source.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(json.dumps(src, ensure_ascii=False, indent=1))


def fetch(a):
    global LIST_ONLY
    LIST_ONLY = a.list
    os.makedirs(a.out, exist_ok=True)
    if ',' in a.item:
        return fetch_many(a, [x.strip() for x in a.item.split(',') if x.strip()])
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
    total = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', raw],
                                 capture_output=True, text=True).stdout.strip() or 0)
    if total and total < a.offset + 120:  # a short recording is taken whole
        a.offset = 0
    if total:
        a.minutes = round(min(a.minutes, (total - a.offset) / 60), 2)
    src['length_s'] = round(total)
    clip = os.path.join(a.out, 'clip.opus')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(a.offset), '-t', str(a.minutes * 60), '-i', raw, '-vn',
                    '-ac', '1', '-ar', str(SR), '-c:a', 'libopus', '-b:a', '32k', clip], check=True)
    os.remove(raw)
    src.update({'clip_offset_s': a.offset, 'clip_minutes': a.minutes})
    json.dump(src, open(os.path.join(a.out, 'source.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(json.dumps(src, ensure_ascii=False, indent=1))


# the passes of the "two ears" test (2026-10-24, the owner: "Yiddish is German and Hebrew — transcribe it
# twice, one in German and one in Hebrew, and Claude curates … remember to use WhisperX"): Whisper hears German
# well and ivrit.ai hears the loshon-kodesh words well; the Yiddish pass (run 6) got neither. Every pass is
# WhisperX (Silero VAD → Whisper → WhisperX's wav2vec2 word aligner). Each pass: model, aligner language.
PASSES = {
    'yi': ('large-v3', 'he'),
    'de': ('large-v3', 'de'),
    'he': ('ivrit-ai/whisper-large-v3-turbo-ct2', 'he'),
    # four ears (2026-10-24, the owner: "do it now the other ears"): Whisper's own translation into English
    # (task translate from Yiddish) — the meaning as a cross-check; no word aligner (English words, Yiddish audio)
    'en': ('large-v3', None),
}
# the vocabulary prompt: Whisper spells the words it was shown far more often (Chabad terms, the sicha's date)
PROMPTS = {
    'de': 'Der Rebbe redt Jiddisch: Chassidus, Moschiach, Gemore, Rambam, Sohar, Toyre, Mitzve, Schabbes, '
          'Jud-Alef Nissen, Jud-Gimel Nissen, Tzemach Tzedek, Rebbe Maharasch, mimale mekoymo, Farbrengen, Ma\'amer.',
    'he': 'הרבי מליובאוויטש בשיחה: חסידות, משיח, גמרא, רמב"ם, זוהר, תורה, מצוה, שבת, י"א ניסן, י"ג ניסן, '
          'הצמח צדק, ממלא מקומו, תפילת ערבית, התוועדות, מאמר.',
    'en': 'The Lubavitcher Rebbe speaks: Chassidus, Moshiach, Gemara, Rambam, Zohar, Torah, mitzvah, Shabbos, '
          '11 Nissan, 13 Nissan, the Tzemach Tzedek, Rebbe Maharash, farbrengen, maamar.',
}
# run 6 filled ~4 min with loops ("אין אין אין…"): faster-whisper's own guards against repetition
ANTI_LOOP = {'repetition_penalty': 1.15, 'no_repeat_ngram_size': 4, 'compression_ratio_threshold': 2.2,
             'log_prob_threshold': -1.0, 'no_speech_threshold': 0.6, 'condition_on_previous_text': False}


def stt(a):
    os.environ.setdefault('SUPABASE_URL', 'http://unused')
    os.environ.setdefault('SUPABASE_SERVICE_KEY', 'unused')
    import whisperx
    from transcribe import cues_of, load_wav, segments_of

    model_name, align_lang = PASSES[a.lang]
    wav = load_wav(os.path.join(a.out, 'clip.opus'))
    dur = len(wav) / SR
    t = time.time()
    translate = a.lang == 'en'
    kw = dict(compute_type='int8', language='yi' if translate else a.lang)
    if translate:
        kw['task'] = 'translate'
    opts = dict(ANTI_LOOP) if a.anti_loop else None
    if a.prompt:
        opts = {**(opts or {}), 'initial_prompt': PROMPTS[a.lang]}
    model = None
    for extra in ({'vad_method': 'silero', 'asr_options': opts}, {'asr_options': opts}, {'vad_method': 'silero'}, {}):
        extra = {k: v for k, v in extra.items() if v is not None}
        try:
            model = whisperx.load_model(model_name, 'cpu', **kw, **extra)
            print(f'WhisperX: {model_name} ({a.lang}) with {sorted(extra)}')
            break
        except (TypeError, ValueError) as err:
            print(f'WhisperX load_model {sorted(extra)} refused: {err}')
    res = model.transcribe(wav, batch_size=8, language=kw['language'], **({'task': 'translate'} if translate else {}))
    t_asr = time.time() - t
    if translate:  # English text over Yiddish audio: the segments' own times, no word aligner
        cues = [[round(sg['start'], 2), round(sg['end'], 2), sg['text'].strip()] for sg in res['segments'] if sg['text'].strip()]
        doc = {'lang': 'en', 'task': 'translate from yi', 'model': model_name, 'anti_loop': bool(a.anti_loop), 'prompt': bool(a.prompt),
               'duration': round(dur), 'asr_s': round(t_asr), 'words': sum(len(c[2].split()) for c in cues), 'cues': cues,
               'word_times': []}
        json.dump(doc, open(os.path.join(a.out, 'stt-en.json'), 'w', encoding='utf8'), ensure_ascii=False)
        print(f'{dur / 60:.1f} min → {len(cues)} English segments; ASR {t_asr:.0f}s')
        for c in cues[:25]:
            print(f'  {c[0]:7.2f} {c[1]:7.2f}  {c[2]}')
        return
    am, meta = whisperx.load_align_model(language_code=align_lang, device='cpu')
    t = time.time()
    al = whisperx.align(res['segments'], am, meta, wav, 'cpu', return_char_alignments=False)
    t_al = time.time() - t
    segs = segments_of(al['segments'])
    cues = cues_of(segs)
    words = [[round(w.start, 2), round(w.end, 2), (w.word or '').strip()] for sg in segs for w in sg.words if (w.word or '').strip()]
    placed = sum(1 for sg in al['segments'] for w in sg.get('words', []) if 'start' in w)
    total = sum(len(sg.get('words', [])) for sg in al['segments'])
    doc = {
        'lang': a.lang, 'model': model_name, 'aligner': f'whisperx wav2vec2 ({align_lang})', 'anti_loop': bool(a.anti_loop), 'prompt': bool(a.prompt),
        'duration': round(dur), 'asr_s': round(t_asr), 'align_s': round(t_al), 'words': total, 'words_placed': placed,
        'cues': cues, 'word_times': words,
    }
    name = 'stt.json' if a.lang == 'yi' else f'stt-{a.lang}.json'
    json.dump(doc, open(os.path.join(a.out, name), 'w', encoding='utf8'), ensure_ascii=False)
    print(f'{dur / 60:.1f} min → {len(cues)} cues, {placed}/{total} words placed by the aligner; ASR {t_asr:.0f}s, align {t_al:.0f}s')
    for c in cues[:25]:
        print(f'  {c[0]:7.2f} {c[1]:7.2f}  {c[2]}')


def mms(a):
    """Meta MMS speech recognition with its Yiddish adapter (facebook/mms-1b-all, target 'yid'): letter by letter
    from the sounds (CTC), so it cannot loop or invent sentences — the tie-breaker between the German and the
    Hebrew ears. 20 s windows; word times from the CTC frames (20 ms each)."""
    import numpy as np
    import torch
    from transformers import AutoProcessor, Wav2Vec2ForCTC

    from transcribe import load_wav

    wav = load_wav(os.path.join(a.out, 'clip.opus'))
    dur = len(wav) / SR
    t = time.time()
    proc = model = None
    # Yiddish, Eastern Yiddish — then Hebrew: run 1 found MMS has no Yiddish adapter ('yid' / 'ydd' unknown);
    # its Hebrew one still writes the sounds in Hebrew letters, letter by letter, without loops
    for code in ('yid', 'ydd', 'heb'):
        try:
            proc = AutoProcessor.from_pretrained('facebook/mms-1b-all', target_lang=code)
            model = Wav2Vec2ForCTC.from_pretrained('facebook/mms-1b-all', target_lang=code, ignore_mismatched_sizes=True)
            print(f'MMS adapter: {code}')
            break
        except Exception as err:
            print(f'MMS adapter {code}: {type(err).__name__} {str(err)[:200]}')
    if model is None:
        try:
            import json as _j
            from huggingface_hub import hf_hub_download
            vocab = _j.load(open(hf_hub_download('facebook/mms-1b-all', 'vocab.json')))
            print('MMS languages starting with y / h:', sorted(k for k in vocab if k[:1] in 'yh'))
        except Exception as err:
            print(f'(could not list the MMS languages: {err})')
        raise SystemExit('MMS: no Yiddish or Hebrew adapter')
    model.eval()
    torch.set_num_threads(os.cpu_count() or 4)
    step = 20 * SR
    words = []
    with torch.inference_mode():
        for s0 in range(0, len(wav), step):
            x = wav[s0:s0 + step]
            if len(x) < SR // 2 or float(np.abs(x).max()) < 1e-3:
                continue
            inp = proc(x, sampling_rate=SR, return_tensors='pt')
            ids = torch.argmax(model(**inp).logits, dim=-1)[0]
            out = proc.tokenizer.decode(ids, output_word_offsets=True)
            fps = ids.shape[0] / (len(x) / SR)
            for w in out.word_offsets:
                words.append([round(s0 / SR + w['start_offset'] / fps, 2), round(s0 / SR + w['end_offset'] / fps, 2), w['word']])
    t_asr = time.time() - t
    # cues of ≤ 6 s / ≤ 90 characters, like the others, for reading
    cues, cur = [], None
    for ws, we, w in words:
        if cur and (we - cur[0] > 6 or len(cur[2]) + len(w) > 90 or ws - cur[1] > 0.8):
            cues.append(cur)
            cur = None
        cur = [ws, we, w] if cur is None else [cur[0], we, cur[2] + ' ' + w]
    if cur:
        cues.append(cur)
    doc = {'lang': 'yi', 'model': f'facebook/mms-1b-all ({code} adapter)', 'duration': round(dur), 'asr_s': round(t_asr),
           'words': len(words), 'cues': cues, 'word_times': words}
    json.dump(doc, open(os.path.join(a.out, 'stt-mms.json'), 'w', encoding='utf8'), ensure_ascii=False)
    print(f'{dur / 60:.1f} min → {len(words)} words, {len(cues)} cues; {t_asr:.0f}s')
    for c in cues[:25]:
        print(f'  {c[0]:7.2f} {c[1]:7.2f}  {c[2]}')


def clean(a):
    """Demucs (htdemucs, two stems): the Rebbe's voice apart from the crowd and the niggunim; clip.opus becomes
    the voice, the original is kept as clip-raw.opus"""
    raw = os.path.join(a.out, 'clip.opus')
    wav_in = os.path.join(a.out, 'clip.wav')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', raw, '-ac', '2', '-ar', '44100', wav_in], check=True)
    t = time.time()
    subprocess.run(['python', '-m', 'demucs', '--two-stems=vocals', '-n', 'htdemucs', '-d', 'cpu', '-o', os.path.join(a.out, 'sep'), wav_in], check=True)
    voice = os.path.join(a.out, 'sep', 'htdemucs', 'clip', 'vocals.wav')
    os.replace(raw, os.path.join(a.out, 'clip-raw.opus'))
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', voice, '-ac', '1', '-ar', str(SR), '-c:a', 'libopus', '-b:a', '32k', raw], check=True)
    subprocess.run(['rm', '-rf', os.path.join(a.out, 'sep'), wav_in])
    print(f'Demucs: the voice separated in {time.time() - t:.0f}s')


def merge(a):
    """the German pass's lines as the frame; under each, the Hebrew pass's words heard in the same seconds —
    the work file Claude curates (printed in full, and written to merged.txt)"""
    de = json.load(open(os.path.join(a.out, 'stt-de.json'), encoding='utf8'))
    he = json.load(open(os.path.join(a.out, 'stt-he.json'), encoding='utf8'))
    src = json.load(open(os.path.join(a.out, 'source.json'), encoding='utf8'))
    clock = lambda s: f'{int(s // 60):02d}:{s % 60:04.1f}'
    frame = de['cues']
    hw = he['word_times']
    taken = [False] * len(hw)
    lines = []
    for i, (s, e, t) in enumerate(frame):
        nxt = frame[i + 1][0] if i + 1 < len(frame) else 1e9
        mine = []
        for j, (ws, we, w) in enumerate(hw):
            mid = (ws + we) / 2
            if not taken[j] and s - 0.4 <= mid < min(nxt, e + 0.4):
                mine.append(w)
                taken[j] = True
        lines.append((s, e, t, ' '.join(mine)))
    # Hebrew words heard where the German pass heard nothing get lines of their own
    groups = []
    for (ws, we, w), k in zip(hw, taken):
        if k:
            continue
        if groups and ws - groups[-1][1] < 1.5 and len(groups[-1][2]) < 14:
            groups[-1][1] = we
            groups[-1][2].append(w)
        else:
            groups.append([ws, we, [w]])
    lines += [(g[0], g[1], '', ' '.join(g[2])) for g in groups]
    lines.sort(key=lambda x: x[0])
    # the other ears, when they ran: Meta MMS Yiddish words by time, Whisper's English by overlap
    extra = {}
    for key, name in (('mms', 'stt-mms.json'), ('en', 'stt-en.json')):
        f = os.path.join(a.out, name)
        if os.path.exists(f):
            extra[key] = json.load(open(f, encoding='utf8'))
    ears = {}
    for key, doc in extra.items():
        items = doc['word_times'] if key == 'mms' else doc['cues']
        per = [[] for _ in lines]
        for ws, we, w in items:
            mid = (ws + we) / 2
            best = None
            for n, (s, e, _, _) in enumerate(lines):
                if s - 0.4 <= mid <= e + 0.4 or (key == 'en' and ws < e and we > s):
                    best = n
                    if key == 'mms':
                        break
                    per[n].append(w)
            if key == 'mms' and best is not None:
                per[best].append(w)
        ears[key] = per
    out = [src.get('title', ''), 'parts: ' + ' · '.join(f'{clock(p["start_s"])} {p["title"]} ({p["file"]})' for p in src.get('parts', [])),
           f'DE = WhisperX {de["model"]} (German) · HE = WhisperX {he["model"]} (Hebrew) · anti-loop {de.get("anti_loop")} · prompt {de.get("prompt")}'
           + (' · MMS = Meta MMS Yiddish' if 'mms' in ears else '') + (' · EN = WhisperX translate' if 'en' in ears else '')
           + (' · audio cleaned by Demucs' if os.path.exists(os.path.join(a.out, 'clip-raw.opus')) else ''), '']
    for n, (s, e, t, h) in enumerate(lines):
        out.append(f'{n}|{clock(s)}-{clock(e)}')
        out.append(f'  DE: {t}')
        out.append(f'  HE: {h}')
        if 'mms' in ears:
            out.append(f'  MMS: {" ".join(ears["mms"][n])}')
        if 'en' in ears:
            out.append(f'  EN: {" / ".join(dict.fromkeys(ears["en"][n]))}')
    text = '\n'.join(out) + '\n'
    open(os.path.join(a.out, 'merged.txt'), 'w', encoding='utf8').write(text)
    print(f'DE {len(frame)} cues ({de["words"]} words, ASR {de["asr_s"]}s) · HE {len(he["cues"])} cues ({he["words"]} words, ASR {he["asr_s"]}s) · {len(groups)} Hebrew-only lines')
    print(text)


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
    ap.add_argument('step', choices=['fetch', 'stt', 'retime', 'merge', 'mms', 'clean'])
    ap.add_argument('--prompt', action='store_true', help='stt: the vocabulary prompt (PROMPTS)')
    ap.add_argument('--lang', default='yi', choices=sorted(PASSES))
    ap.add_argument('--anti-loop', action='store_true')
    ap.add_argument('--url', default='')
    ap.add_argument('--item', default='')
    ap.add_argument('--minutes', type=float, default=20)
    ap.add_argument('--offset', type=float, default=60)
    ap.add_argument('--out', default='out/rebbe')
    ap.add_argument('--list', action='store_true', help='fetch: only list archive.org candidates')
    a = ap.parse_args()
    {'fetch': fetch, 'stt': stt, 'retime': retime, 'merge': merge, 'mms': mms, 'clean': clean}[a.step](a)


if __name__ == '__main__':
    main()
