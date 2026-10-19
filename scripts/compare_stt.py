"""
compare_stt.py — WhisperX against Whisper (ivrit.ai) + Meta MMS on the same Hebrew lesson (2026-10-19, the
owner: "Whisper X is not better at listening to Hebrew? lets do a test comparison").

  python scripts/compare_stt.py run   --variant A|B|C --id ID --audio cmp.opus --out out/cmp
  python scripts/compare_stt.py score --id ID --clip 720 --dir out/cmp

  A  WhisperX stock: large-v3 + WhisperX's Hebrew aligner (imvladikon/wav2vec2-xls-r-300m-hebrew)
  B  WhisperX with ivrit.ai's Hebrew Whisper + the same aligner
  C  ours: ivrit.ai's Hebrew Whisper (faster-whisper) + Meta MMS forced alignment (align.py)

Every variant ends as words with a time; `score` compares them with YouTube's captions of the same
minutes (themselves automatic — a yardstick, not the truth): word error rate, and how far each matched
word's time is from YouTube's.
"""
import argparse
import difflib
import json
import os
import re
import statistics
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

SR = 16000
IVRIT = 'ivrit-ai/whisper-large-v3-turbo-ct2'


def load_wav(path):
    import numpy as np

    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype('float32') / 32768.0


def run_whisperx(model_name, wav):
    import whisperx

    try:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language='he', vad_method='silero')
    except TypeError:
        model = whisperx.load_model(model_name, 'cpu', compute_type='int8', language='he')
    t = time.time()
    res = model.transcribe(wav, batch_size=8, language='he')
    t_asr = time.time() - t
    am, meta = whisperx.load_align_model(language_code='he', device='cpu')
    t = time.time()
    al = whisperx.align(res['segments'], am, meta, wav, 'cpu', return_char_alignments=False)
    t_al = time.time() - t
    words = []
    for seg in al['segments']:
        for w in seg.get('words', []):
            if 'start' in w:
                words.append([round(w['start'], 2), round(w['end'], 2), w['word'].strip()])
            else:  # words the aligner could not place keep the segment's time
                words.append([round(seg['start'], 2), round(seg['end'], 2), w['word'].strip()])
    return words, {'asr_s': round(t_asr), 'align_s': round(t_al), 'aligner': meta.get('language', 'he') if isinstance(meta, dict) else 'he'}


def spread(cues):
    """line-level cues → words, times spread over the line by length (the reference and variant C)"""
    out = []
    for s, e, text in cues:
        ws = text.split()
        if not ws:
            continue
        total = sum(len(w) for w in ws) or 1
        t = s
        for w in ws:
            d = (e - s) * len(w) / total
            out.append([round(t, 2), round(t + d, 2), w])
            t += d
    return out


def run_ours(wav, vid, audio):
    import transcribe as tr
    import align as mms
    from faster_whisper import WhisperModel

    model = WhisperModel(IVRIT, device='cpu', compute_type='int8', cpu_threads=os.cpu_count() or 4)
    t = time.time()
    segs, _ = model.transcribe(wav, language='he', beam_size=5, vad_filter=True, word_timestamps=True, condition_on_previous_text=False)
    cues = tr.cues_of(list(segs))
    t_asr = time.time() - t
    mms.load()
    t = time.time()
    new, _, _ = mms.align(cues, wav)
    t_al = time.time() - t
    return spread(new), {'asr_s': round(t_asr), 'align_s': round(t_al), 'cues_whisper': cues, 'cues_mms': new}


def norm(w):
    w = re.sub(r'[֑-ׇ]', '', w)  # points and accents
    w = re.sub(r'[^א-תa-zA-Z0-9]', '', w)
    return w


def score_one(sys_words, ref_words):
    a = [norm(w[2]) for w in ref_words]
    b = [norm(w[2]) for w in sys_words]
    ai = [i for i, x in enumerate(a) if x]
    bi = [i for i, x in enumerate(b) if x]
    A = [a[i] for i in ai]
    B = [b[i] for i in bi]
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    errs = 0
    deltas = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for k in range(i2 - i1):
                deltas.append(sys_words[bi[j1 + k]][0] - ref_words[ai[i1 + k]][0])
        else:
            errs += max(i2 - i1, j2 - j1)
    ad = sorted(abs(d) for d in deltas)
    return {
        'ref_words': len(A),
        'sys_words': len(B),
        'wer_vs_youtube': round(errs / max(len(A), 1), 3),
        'matched': len(deltas),
        'time_median_s': round(statistics.median(deltas), 2) if deltas else None,
        'time_abs_median_s': round(statistics.median(ad), 2) if ad else None,
        'within_1s': round(sum(d <= 1 for d in ad) / len(ad), 3) if ad else None,
        'within_2s': round(sum(d <= 2 for d in ad) / len(ad), 3) if ad else None,
    }


def kv_get(key):
    supa = os.environ['SUPABASE_URL'].rstrip('/')
    k = os.environ['SUPABASE_SERVICE_KEY']
    q = urllib.parse.quote(key, safe='')
    req = urllib.request.Request(f'{supa}/rest/v1/global_options?select=value&key=eq.{q}', headers={'apikey': k, 'authorization': f'Bearer {k}'})
    rows = json.load(urllib.request.urlopen(req, timeout=60))
    v = rows[0]['value'] if rows else None
    return json.loads(v) if isinstance(v, str) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'score'])
    ap.add_argument('--variant')
    ap.add_argument('--id', required=True)
    ap.add_argument('--audio')
    ap.add_argument('--clip', type=float, default=720)
    ap.add_argument('--out', default='out/cmp')
    ap.add_argument('--dir', default='out/cmp')
    a = ap.parse_args()
    if a.cmd == 'run':
        os.makedirs(a.out, exist_ok=True)
        wav = load_wav(a.audio)
        t0 = time.time()
        if a.variant == 'A':
            words, info = run_whisperx('large-v3', wav)
        elif a.variant == 'B':
            words, info = run_whisperx(IVRIT, wav)
        else:
            words, info = run_ours(wav, a.id, a.audio)
        info['total_s'] = round(time.time() - t0)
        info['audio_s'] = round(len(wav) / SR)
        json.dump({'variant': a.variant, 'words': words, **info}, open(f'{a.out}/{a.variant}.json', 'w', encoding='utf8'), ensure_ascii=False)
        print(f'{a.variant}: {len(words)} words, {info}' if a.variant != 'C' else f'C: {len(words)} words, asr {info["asr_s"]}s, mms {info["align_s"]}s')
        return
    row = kv_get(f'videos/transcript/{a.id}')
    ref_cues = [c for c in (row.get('cuesOrig') or row['cues']) if c[0] < a.clip - 2]
    ref = spread(ref_cues)
    names = {'A': 'WhisperX (large-v3 + wav2vec2-hebrew)', 'B': 'WhisperX (ivrit.ai + wav2vec2-hebrew)', 'C': 'Whisper ivrit.ai + Meta MMS'}
    report = {'id': a.id, 'clip_s': a.clip, 'reference': 'YouTube captions (automatic)', 'variants': {}}
    for v in 'ABC':
        p = f'{a.dir}/{v}.json'
        if not os.path.exists(p):
            p = next((os.path.join(r, f) for r, _, fs in os.walk(a.dir) for f in fs if f == f'{v}.json'), None)
        if not p:
            continue
        d = json.load(open(p, encoding='utf8'))
        sw = [w for w in d['words'] if w[0] < a.clip - 2]
        s = score_one(sw, ref)
        s.update({'name': names[v], 'cpu_s': d.get('total_s'), 'asr_s': d.get('asr_s'), 'align_s': d.get('align_s')})
        report['variants'][v] = s
        report.setdefault('text', {})[v] = ' '.join(w[2] for w in sw)
        report.setdefault('words', {})[v] = sw
    report['text']['YT'] = ' '.join(w[2] for w in ref)
    report['words']['YT'] = ref
    json.dump(report, open(f'{a.dir}/report.json', 'w', encoding='utf8'), ensure_ascii=False)
    print(f'{"":42} {"WER":>6} {"|Δt| med":>9} {"≤1s":>6} {"≤2s":>6} {"Δt med":>7} {"CPU s":>6}')
    for v, s in report['variants'].items():
        print(f'{v} {s["name"]:40} {s["wer_vs_youtube"]:>6} {s["time_abs_median_s"]!s:>9} {s["within_1s"]!s:>6} {s["within_2s"]!s:>6} {s["time_median_s"]!s:>7} {s["cpu_s"]!s:>6}')


if __name__ == '__main__':
    main()
