"""
tag_quotes.py — mark, in a lesson's subtitles, the moments the rabbi quotes a source, each tagged with
its own kind (2026-10-21, the owner: "all Rav Meir Elyahu's shiurim translations and Hebrew … tagged at
each quote … Talmud and the Book and Chapter and Number … one for Talmud and other for Zohar and so on …
so when we see the subtitles we could change the colors").

  python scripts/tag_quotes.py --lane N --lanes L --ids-file data/quote-ids.txt [--force] [--ids a,b]

The curated lesson already lists its sources: [seconds, kind, reference, gist, (1 = approximate)].
For each source:
  1. the reference → Sefaria (name API, with a table of the Portuguese / Hebrew spellings the curation
     uses) → the Hebrew text of that verse / daf / paragraph;
  2. that text is looked for in the Hebrew cues around the source's moment (−40 s … +120 s): words
     compared by their consonant skeleton (no points, final letters folded, vav/yod dropped — the
     transcript spells by sound), a word counts when it starts or ends a pair that the source also has,
     and the longest run of such words (gaps of ≤ 2) is the quote;
  3. no text or no run → the cue at the moment itself is tagged (how: "time").
Kinds: tanakh, mishnah, talmud, midrash, zohar (Zohar, Tikunim, the Ari), halacha, comentario, outro.

Writes videos/transcript/<id>/quotes = { v: 1, quotes: [{ t, kind, ref, sefaria, gist, how, score,
cues: [c0, c1], words: [[cue, w0, w1], …] }] } — cues index the transcript (the pt / en translations
have one line per cue, so a cue range colours them too); words index the Hebrew cue split on spaces.
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

SUPA = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')
H = {'apikey': KEY, 'authorization': f'Bearer {KEY}'}
UA = {'user-agent': 'emunah-caption-harvest quote tagger (shiur-hebraico.vercel.app)'}


def kv_get(key):
    q = urllib.parse.quote(key, safe='')
    req = urllib.request.Request(f'{SUPA}/rest/v1/global_options?select=value&key=eq.{q}', headers=H)
    rows = json.load(urllib.request.urlopen(req, timeout=90))
    v = rows[0]['value'] if rows else None
    return json.loads(v) if isinstance(v, str) else v


def kv_put(key, value):
    body = json.dumps([{'key': key, 'value': value}], ensure_ascii=False).encode('utf8')
    req = urllib.request.Request(
        f'{SUPA}/rest/v1/global_options?on_conflict=key', data=body, method='POST',
        headers={**H, 'content-type': 'application/json', 'prefer': 'resolution=merge-duplicates,return=minimal'},
    )
    urllib.request.urlopen(req, timeout=90)


def lane_of(vid, lanes):
    h = 7
    for ch in vid:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % lanes


# ── the kind of a source ──────────────────────────────────────────────────────────────────────────
def kind_of(kind, ref):
    r = strip_accents(ref).lower()
    if kind == 'talmud' and re.match(r'\s*(mishna|mishnah)\b', r):
        return 'mishnah'
    if kind == 'talmud' and re.match(r'\s*pirkei avot|\s*avot\b', r):
        return 'mishnah'
    if kind in ('tanakh', 'talmud', 'midrash', 'zohar', 'halacha', 'comentario'):
        return kind
    if re.search(r'\b(zohar|tikun|arizal|ari hakadosh|shaar hagilgulim|etz chaim)', r):
        return 'zohar'
    return 'outro'


# ── references → Sefaria ──────────────────────────────────────────────────────────────────────────
def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


BOOKS = {
    # Tanakh (the curation writes the Hebrew names)
    'bereshit': 'Genesis', 'shemot': 'Exodus', 'vayikra': 'Leviticus', 'bamidbar': 'Numbers', 'devarim': 'Deuteronomy',
    'yehoshua': 'Joshua', 'shoftim': 'Judges', 'shmuel i': 'I Samuel', 'shmuel ii': 'II Samuel', 'shmuel 1': 'I Samuel',
    'shmuel 2': 'II Samuel', 'melachim i': 'I Kings', 'melachim ii': 'II Kings', 'melachim 1': 'I Kings', 'melachim 2': 'II Kings',
    'yeshaia': 'Isaiah', 'yeshayahu': 'Isaiah', 'yeshayah': 'Isaiah', 'yirmiyahu': 'Jeremiah', 'yirmiya': 'Jeremiah',
    'yechezkel': 'Ezekiel', 'hoshea': 'Hosea', 'yoel': 'Joel', 'amos': 'Amos', 'ovadia': 'Obadiah', 'yona': 'Jonah',
    'micha': 'Micah', 'nachum': 'Nahum', 'chavakuk': 'Habakkuk', 'tzefania': 'Zephaniah', 'chagai': 'Haggai',
    'zecharia': 'Zechariah', 'malachi': 'Malachi', 'tehilim': 'Psalms', 'tehillim': 'Psalms', 'mishlei': 'Proverbs',
    'iyov': 'Job', 'shir hashirim': 'Song of Songs', 'rut': 'Ruth', 'eicha': 'Lamentations', 'kohelet': 'Ecclesiastes',
    'ester': 'Esther', 'meguilat ester': 'Esther', 'daniel': 'Daniel', 'ezra': 'Ezra', 'nechemia': 'Nehemiah',
    'divrei hayamim i': 'I Chronicles', 'divrei hayamim ii': 'II Chronicles',
    # Talmud
    'berachot': 'Berakhot', 'shabat': 'Shabbat', 'eruvin': 'Eruvin', 'pesachim': 'Pesachim', 'yoma': 'Yoma',
    'suca': 'Sukkah', 'sukka': 'Sukkah', 'beitza': 'Beitzah', 'rosh hashana': 'Rosh Hashanah', 'taanit': 'Taanit',
    'meguila': 'Megillah', 'megila': 'Megillah', 'moed katan': 'Moed Katan', 'chaguiga': 'Chagigah', 'chagiga': 'Chagigah',
    'yevamot': 'Yevamot', 'ketubot': 'Ketubot', 'nedarim': 'Nedarim', 'nazir': 'Nazir', 'sota': 'Sotah', 'gitin': 'Gittin',
    'kidushin': 'Kiddushin', 'bava kama': 'Bava Kamma', 'bava metzia': 'Bava Metzia', 'bava batra': 'Bava Batra',
    'sanhedrin': 'Sanhedrin', 'makot': 'Makkot', 'shevuot': 'Shevuot', 'avoda zara': 'Avodah Zarah', 'horayot': 'Horayot',
    'zevachim': 'Zevachim', 'menachot': 'Menachot', 'chulin': 'Chullin', 'bechorot': 'Bekhorot', 'arachin': 'Arakhin',
    'temura': 'Temurah', 'keritot': 'Keritot', 'meila': 'Meilah', 'tamid': 'Tamid', 'nida': 'Niddah',
    'pirkei avot': 'Pirkei Avot', 'avot': 'Pirkei Avot',
    # Midrash
    'bereshit raba': 'Bereshit Rabbah', 'bereshit rabba': 'Bereshit Rabbah', 'shemot raba': 'Shemot Rabbah',
    'vayikra raba': 'Vayikra Rabbah', 'bamidbar raba': 'Bamidbar Rabbah', 'devarim raba': 'Devarim Rabbah',
    'midrash tanchuma': 'Midrash Tanchuma', 'tanchuma': 'Midrash Tanchuma',
    # Halacha
    'shulchan arukh, orach chaim': 'Shulchan Arukh, Orach Chayim', 'shulchan aruch, orach chaim': 'Shulchan Arukh, Orach Chayim',
    'shulchan arukh, yore dea': "Shulchan Arukh, Yoreh De'ah", 'shulchan arukh, yoreh deah': "Shulchan Arukh, Yoreh De'ah",
    'shulchan arukh, even haezer': 'Shulchan Arukh, Even HaEzer', 'shulchan arukh, choshen mishpat': 'Shulchan Arukh, Choshen Mishpat',
}
RAMBAM = {
    'hilchot teshuva': 'Repentance', 'hilchot yesodei hatora': 'Foundations of the Torah', 'yesodei hatora': 'Foundations of the Torah',
    'hilchot deot': 'Human Dispositions', 'hilchot talmud tora': 'Torah Study', 'hilchot sanhedrin': 'The Sanhedrin and the Penalties within their Jurisdiction',
    'hilchot shabat': 'Sabbath', 'hilchot tefila': 'Prayer and the Priestly Blessing', 'hilchot chametz umatza': 'Leavened and Unleavened Bread',
    'hilchot melachim': 'Kings and Wars', 'hilchot avoda zara': 'Foreign Worship and Customs of the Nations', 'hilchot ishut': 'Marriage',
    'hilchot isurei bia': 'Forbidden Intercourse', 'hilchot matnot aniyim': 'Gifts to the Poor', 'hilchot berachot': 'Blessings',
}
_cache = {}


def http_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=40))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    return None


def candidates(ref):
    """the curation's reference → spellings Sefaria may know, most specific first"""
    r = strip_accents(ref)
    r = re.sub(r'\(.*?\)', '', r)  # "(Tosafot)", "(Rabi Akiva)"
    r = re.sub(r'\s*[;|].*$', '', r)  # "Berachot 40a; Sanhedrin 70a" → the first
    r = re.sub(r'\bp\.\s*\d+.*$', '', r)
    r = re.sub(r'\s+', ' ', r).strip(' ,.')
    out = []
    low = r.lower()
    m = re.match(r'(?:rambam,\s*)?(?:mishne tora,\s*)?(hilchot [a-z ]+?|yesodei hatora)\s+(\d+[:.]\d+)', low)
    if m and m.group(1).strip() in RAMBAM:
        out.append(f'Mishneh Torah, {RAMBAM[m.group(1).strip()]} {m.group(2).replace(".", ":")}')
    for k in sorted(BOOKS, key=len, reverse=True):
        if low.startswith(k + ' ') or low.startswith(k + ','):
            out.append(BOOKS[k] + r[len(k):].lstrip(',') if ',' not in k else BOOKS[k] + r[len(k):])
            break
    m = re.match(r'(mishna|mishnah)\s+(.+)$', low)
    if m:
        rest = r[len(m.group(1)):].strip()
        for k in sorted(BOOKS, key=len, reverse=True):
            if rest.lower().startswith(k + ' '):
                out.append('Mishnah ' + BOOKS[k] + rest[len(k):])
                break
    out.append(r)
    seen = []
    for c in out:
        c = re.sub(r'\s+', ' ', c).strip()
        if c and c not in seen:
            seen.append(c)
    return seen


def he_text(t):
    if isinstance(t, list):
        return ' '.join(he_text(x) for x in t)
    return re.sub(r'<[^>]+>', ' ', t or '')


def sefaria(ref):
    """(sefaria ref, Hebrew text) or (None, '')"""
    if ref in _cache:
        return _cache[ref]
    found = (None, '')
    for c in candidates(ref):
        if not re.search(r'\d', c):
            continue  # a book's name alone is no quote
        j = http_json('https://www.sefaria.org/api/name/' + urllib.parse.quote(c) + '?limit=0')
        time.sleep(0.15)
        if not j or not j.get('is_ref'):
            continue
        sref = j.get('ref') or c
        t = http_json('https://www.sefaria.org/api/v3/texts/' + urllib.parse.quote(sref) + '?version=hebrew&return_format=text_only')
        time.sleep(0.15)
        vs = (t or {}).get('versions') or []
        txt = he_text(vs[0].get('text')) if vs else ''
        if len(txt) > 20:
            found = (sref, txt[:20000])
            break
    _cache[ref] = found
    return found


# ── matching ──────────────────────────────────────────────────────────────────────────────────────
FINALS = str.maketrans('ךםןףץ', 'כמנפצ')


def skel(w):
    w = re.sub(r'[֑-ׇ]', '', w)
    w = re.sub(r'[^א-ת]', '', w).translate(FINALS)
    if len(w) > 2:
        w = w[0] + re.sub(r'[וי]', '', w[1:])
    return w


# words every lesson and every daf has — a pair of two of them proves nothing ("הקדוש ברוך הוא",
# "אמר רבי", "של זה"…); skeletons, as skel() makes them (first run, 2026-10-21: score-3 Talmud runs were
# mostly "הקדוש ברוך הוא")
COMMON = {skel(w) for w in (
    'הקדוש ברוך הוא אמר אמרו רבי רב רבן של את על זה זו לא כל אם אבל מה מי כי גם או אין יש היה הם הן אני אתה '
    'אנחנו לו לה להם בו בה עם אל כן כך אז עוד רק כמו שם עד אחד אחת שני דבר אומר אומרת ואמר תני תנא אמר '
    'דאמר מאי היכי הכא התם איכא ליכא דהא והא ולא וכל שהוא שהיא אותו אותה הזה הזאת שלו שלה ישראל ה'
).split()}


def find(cues, t, text):
    """the best run of quoted words near t → (score, [(cue, w0, w1)…]) or None"""
    src = [skel(w) for w in text.split()]
    src = [w for w in src if w]
    pairs = {p for p in zip(src, src[1:]) if not (p[0] in COMMON and p[1] in COMMON)}
    if len(pairs) < 2:
        return None
    need = 3 if len(src) <= 60 else 4  # a whole daf or chapter: more words to be sure
    words = []  # (cue, index in cue, skeleton)
    for ci, c in enumerate(cues):
        if c[0] < t - 40 or c[0] > t + 120:
            continue
        for wi, w in enumerate(c[2].split()):
            s = skel(w)
            if s:
                words.append((ci, wi, s))
    hit = [False] * len(words)
    for i in range(len(words) - 1):
        if (words[i][2], words[i + 1][2]) in pairs:
            hit[i] = hit[i + 1] = True
    best = None
    i = 0
    while i < len(words):
        if not hit[i]:
            i += 1
            continue
        j, gap, n, last = i, 0, 0, i
        while j < len(words) and gap <= 2:
            if hit[j]:
                n += 1
                gap = 0
                last = j
            else:
                gap += 1
            j += 1
        if n >= need:
            start_t = cues[words[i][0]][0]
            key = (n, -abs(start_t - t))
            if not best or key > best[0]:
                best = (key, i, last)
        i = last + 1
    if not best:
        return None
    (n, _), a, b = best
    spans = {}
    for ci, wi, _ in words[a:b + 1]:
        lo, hi = spans.get(ci, (wi, wi))
        spans[ci] = (min(lo, wi), max(hi, wi))
    return n, [[ci, lo, hi] for ci, (lo, hi) in sorted(spans.items())]


def cue_at(cues, t):
    for i, c in enumerate(cues):
        if c[1] > t:
            return i
    return len(cues) - 1


def tag(vid):
    doc = kv_get(f'videos/transcript/{vid}')
    if not doc or not doc.get('cues') or not doc.get('sources'):
        return None
    cues = doc['cues']
    out = []
    for s in doc['sources']:
        t, kind, ref = float(s[0]), s[1], s[2]
        gist = s[3] if len(s) > 3 else ''
        k = kind_of(kind, ref)
        sref, txt = sefaria(ref) if k != 'outro' else (None, '')
        got = find(cues, t, txt) if txt else None
        if got:
            n, words = got
            out.append({'t': t, 'kind': k, 'ref': ref, 'sefaria': sref, 'gist': gist, 'how': 'text', 'score': n,
                        'cues': [words[0][0], words[-1][0]], 'words': words})
        else:
            ci = cue_at(cues, t)
            out.append({'t': t, 'kind': k, 'ref': ref, 'sefaria': sref, 'gist': gist, 'how': 'time', 'score': 0,
                        'cues': [ci, ci], 'words': []})
    out.sort(key=lambda q: (q['cues'][0], q['t']))
    return {'v': 1, 'videoId': vid, 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'quotes': out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lane', type=int, default=1)
    ap.add_argument('--lanes', type=int, default=1)
    ap.add_argument('--ids-file', default='data/quote-ids.txt')
    ap.add_argument('--ids', default='')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry', action='store_true', help='print, do not write')
    a = ap.parse_args()
    ids = [x for x in a.ids.split(',') if x] or [l.strip() for l in open(a.ids_file, encoding='utf8') if l.strip()]
    ids = [v for v in ids if a.ids or lane_of(v, a.lanes) == a.lane - 1]
    print(f'lane {a.lane}/{a.lanes}: {len(ids)} lessons', flush=True)
    tot = {'text': 0, 'time': 0}
    for vid in ids:
        if not a.force and not a.dry and kv_get(f'videos/transcript/{vid}/quotes'):
            print(f'{vid}: tagged already')
            continue
        try:
            res = tag(vid)
        except Exception as e:  # one lesson must not stop the lane
            print(f'{vid}: ✗ {str(e)[:120]}', flush=True)
            continue
        if not res:
            print(f'{vid}: no sources')
            continue
        n_text = sum(q['how'] == 'text' for q in res['quotes'])
        tot['text'] += n_text
        tot['time'] += len(res['quotes']) - n_text
        if a.dry:
            for q in res['quotes']:
                print(f"  {q['kind']:10} {q['how']:4} {q['score']:3} cues {q['cues']} {q['ref'][:40]} → {q['sefaria']}")
        else:
            kv_put(f'videos/transcript/{vid}/quotes', res)
        print(f'{vid}: {len(res["quotes"])} quotes, {n_text} found in the words', flush=True)
    print(f'done: {tot["text"]} quotes found in the words, {tot["time"]} by time only')


if __name__ == '__main__':
    sys.exit(main())
