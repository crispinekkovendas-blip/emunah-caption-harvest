"""The Rebbe model, dataset step 4: Claude curates the three ears into the Rebbe's own Yiddish.

2026-10-28 (the owner: "Go ahead, let's train this"). What WhisperX German, WhisperX Hebrew (ivrit.ai) and Meta
MMS heard in a chunk (rebbe_ears.py → stt-de/he/mms.json) goes to Claude as one timeline, 8 minutes at a time;
Claude writes what the Rebbe said, line by line, as in video-batches/stt-test/rebbe/curated-sample.md:
✓ = the ears agree and every word is sure (these lines become training examples), ~ = the gist is sure, the
wording reconstructed (kept for reading, not for training). What no ear supports is left out.

Claude runs through Claude Code (`claude -p`, no tools, one request per window) with the repository secret
CLAUDE_CODE_OAUTH_TOKEN, like translate-batch.yml.

    python scripts/rebbe_curate.py --out out/ears      → curated.json, curated.txt
"""
import argparse
import json
import os
import re
import subprocess

WINDOW = 480.0
MODEL = os.environ.get('CURATE_MODEL', 'sonnet')
EARS = (('de', 'DE'), ('he', 'HE'), ('mms', 'MMS'))
# the German ear recites its vocabulary prompt in pauses (four-ears run)
PROMPT_ECHO = re.compile(r'Rebbe redt Jiddisch|Chassidus, Moschiach|Tzemach Tzedek, Rebbe Maharasch', re.I)

SYSTEM = """You curate transcripts of the Lubavitcher Rebbe (Rabbi Menachem Mendel Schneerson) speaking Yiddish at a \
farbrengen or sicha, recorded 1970s–1990s. Three speech recognisers ("ears") heard the same audio; none of them \
knows Yiddish:
- DE: Whisper in German mode. Writes the Yiddish by sound in Latin letters ("bechol rega v'rega", "zu a yesh"); good \
on the Germanic words. In silences it may recite its prompt ("Der Rebbe redt Jiddisch, Chassidus, Moschiach…") — \
ignore such text.
- HE: Whisper fine-tuned for Hebrew (ivrit.ai). Writes the Yiddish by sound in Hebrew letters ("ניתין מוקים וניתין \
זמן" = ניט אין מקום און ניט אין זמן); good on the loshon-kodesh words, quotes and names.
- MMS: Meta MMS, letter by letter in Hebrew letters, no punctuation; rough but never invents whole sentences — use \
it to break ties.
Each input line is: start–end seconds, the ear, what it heard.

Write what the Rebbe actually said, in Yiddish, in Hebrew letters:
- Standard Chabad Yiddish spelling as in Sefer HaSichos: Germanic words with אַ אָ וו יי ײַ (וואָס, אַז, דאָס, איז, \
ווערט); loshon-kodesh words in their Hebrew spelling (ענין, בפשטות, הקב"ה, גאולה האמיתית והשלימה); quotes as \
written in their source.
- Verbatim: his words in his order, repetitions included. Never add, explain, smooth or complete from memory of \
the published texts. If you cannot tell what he said, leave it out.
- One line per phrase, 2–15 seconds, its start and end taken from the ears' times.
- Mark each line: ✓ only when the ears support every word and you are sure of it; ~ when the meaning is sure but \
some wording is reconstructed. Do not write lines you would mark lower than ~.
- Leave out singing (niggunim), the crowd, other speakers (chazzan, translators, gabbaim) and the prompt echo.

Example lines (from an earlier curation, Leil 13 Nissan 5751):
639.0	644.5	✓	ממטה למעלה — וואָס דאָס איז דער ענין התפילה בפשטות
674.0	680.0	✓	אַז יעדער ענין ווערט נתהווה בכל רגע ורגע
680.5	690.0	✓	מאין ואפס ממש צו אַ יש, ביז צו יש הממשי, ביז צו יש האמיתי
667.0	673.5	~	בכל רגע ורגע, כמדובר כמה פעמים, ובפרט לאחרי (תורת) הבעל שם טוב

Reply with ONLY the curated lines, one per line: start<TAB>end<TAB>mark<TAB>Yiddish text — seconds with one \
decimal, no other text, no code fences. If the window holds no speech of the Rebbe you can curate, reply NONE."""

LINE = re.compile(r'^\s*(\d+(?:\.\d+)?)\t(\d+(?:\.\d+)?)\t([✓~])\t(.+?)\s*$')


def timeline(out):
    rows = []
    for key, tag in EARS:
        path = os.path.join(out, f'stt-{key}.json')
        if not os.path.exists(path):
            print(f'(no {tag} ear: {path})')
            continue
        for s, e, t in json.load(open(path, encoding='utf8'))['cues']:
            t = t.strip()
            if t and not (tag == 'DE' and PROMPT_ECHO.search(t)):
                rows.append((float(s), float(e), tag, t))
    return sorted(rows)


def ask(text):
    r = subprocess.run(['claude', '-p', 'Curate the ears below following the system rules.', '--system-prompt', SYSTEM,
                        '--tools', '', '--model', MODEL, '--output-format', 'json'],
                       input=text, capture_output=True, text=True, timeout=1800)
    try:
        j = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None, {'error': (r.stderr or r.stdout)[:300]}
    if j.get('is_error'):
        return None, {'error': str(j.get('result'))[:300]}
    return str(j.get('result') or ''), {k: j.get(k) for k in ('total_cost_usd', 'usage', 'duration_ms')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/ears')
    a = ap.parse_args()
    src = json.load(open(os.path.join(a.out, 'source.json'), encoding='utf8'))
    rows = timeline(a.out)
    if not rows:
        raise SystemExit('no ear heard anything')
    end = max(e for _, e, _, _ in rows)
    lines, windows = [], []
    w0 = 0.0
    while w0 < end:
        w1 = w0 + WINDOW
        mine = [r for r in rows if w0 <= r[0] < w1]
        if len(mine) < 3:
            w0 = w1
            continue
        text = '\n'.join(f'{s:.1f}–{e:.1f}\t{tag}\t{t}' for s, e, tag, t in mine)
        reply, meta = ask(text)
        got = []
        for l in (reply or '').splitlines():
            m = LINE.match(l)
            if m and w0 - 5 <= float(m.group(1)) < w1 + 5 and float(m.group(2)) > float(m.group(1)):
                got.append({'start': float(m.group(1)), 'end': float(m.group(2)), 'mark': m.group(3), 'text': m.group(4)})
        windows.append({'from': w0, 'to': w1, 'ear_lines': len(mine), 'curated': len(got), **meta})
        print(f'window {w0 / 60:.0f}–{w1 / 60:.0f} min: {len(mine)} ear lines → {len(got)} curated '
              f'({sum(g["mark"] == "✓" for g in got)} ✓){"  " + meta["error"] if "error" in meta else ""}')
        lines += got
        w0 = w1
    lines.sort(key=lambda l: l['start'])
    sure = [l for l in lines if l['mark'] == '✓']
    secs = sum(l['end'] - l['start'] for l in sure)
    doc = {'source': src, 'model': MODEL, 'windows': windows, 'lines': lines,
           'sure_lines': len(sure), 'sure_seconds': round(secs)}
    json.dump(doc, open(os.path.join(a.out, 'curated.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    off = src.get('clip_offset_s', 0)
    clock = lambda s: f'{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:04.1f}'
    with open(os.path.join(a.out, 'curated.txt'), 'w', encoding='utf8') as f:
        for l in lines:
            f.write(f'{clock(off + l["start"])}  {l["mark"]}  {l["text"]}\n')
    print(f'\n{len(lines)} curated lines, {len(sure)} ✓ = {secs / 60:.1f} min of training speech')
    print(open(os.path.join(a.out, 'curated.txt'), encoding='utf8').read())


if __name__ == '__main__':
    main()
