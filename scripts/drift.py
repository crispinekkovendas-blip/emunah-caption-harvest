"""
drift.py — find, and repair without AI, the stretches where a lesson's translation runs ahead of (or
behind) its Hebrew lines (2026-10-21, the owner: "do 2 and 3, starting with Rav Meir Elyahu").

Found on 2026-10-14/15: with 450-line requests Claude sometimes put the next lines' content into earlier
lines (minute 22 of nEeDpt7qtTI: 6 lines ahead), then spread the rest so the counts still match. The
Hebrew clock is right (Meta's aligner moved nothing); only the translation slips. Requests are 120 lines
since 38eb27f; this mends the lessons made before.

  python scripts/drift.py measure --lane N --lanes L --ids-file data/drift-ids.txt --out out/drift
  python scripts/drift.py repair  --lane N --lanes L --ids-file data/drift-ids.txt --out out/drift [--dry]

Anchors: names and terms that keep their sound in both languages (David / דוד, Midrash / מדרש, Re'em /
ראם). Both sides become consonant skeletons (the Hebrew through uroman); each translated anchor is
matched to the nearest Hebrew line within ±15 with the same skeleton; lag = line difference (positive =
translation ahead).

measure: per lesson and language, the lag of every anchor, the median per 60-line window, and the
stretches whose rolling lag (median of 9 anchors) is ≥ 2 lines → out/drift/<lane>.json.

repair: only those stretches (widened by 12 lines). Inside, the translated words are laid end to end and
cut again: every anchor word whose Hebrew line is known is pinned to that line (only anchors in
increasing order — a longest increasing run — so nothing crosses), and the words between two pins are
shared over the lines between them in proportion to the Hebrew length of each line, a cut moved to the
nearest punctuation within 3 words. The stretch's first and last lines keep their outer edges, so the
rest of the lesson is untouched. The old texts are kept at videos/transcript/<id>/<lang>/before-drift
(written once), the new ones replace videos/transcript/<id>/<lang>; measured again afterwards.
"""
import argparse
import bisect
import json
import os
import re
import statistics
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

SUPA = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')
H = {'apikey': KEY, 'authorization': f'Bearer {KEY}'}
R = 15  # how far (lines) an anchor may sit from its Hebrew line
DRIFT = 2  # lines of rolling lag that count as a drift
STOP = set('para pela pelo como isso essa esse este esta mais muito quando entao ainda porque sobre entre depois antes todos todas tudo nada sempre aqui onde quem qual quer disse dizer fazer outro outra '
           'this that with from they them there then when what which have will would about after before because every other where while these those their'.split())

_uro = None


def uro():
    global _uro
    if _uro is None:
        import uroman as ur

        _uro = ur.Uroman()
    return _uro


def kv_get(key):
    q = urllib.parse.quote(key, safe='')
    for i in range(3):
        try:
            req = urllib.request.Request(f'{SUPA}/rest/v1/global_options?select=value&key=eq.{q}', headers=H)
            rows = json.load(urllib.request.urlopen(req, timeout=90))
            v = rows[0]['value'] if rows else None
            return json.loads(v) if isinstance(v, str) else v
        except Exception:
            time.sleep(5 * (i + 1))
    raise RuntimeError(f'Supabase read failed: {key}')


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


# ── anchors ──────────────────────────────────────────────────────────────────────────────────────
def skel(w):
    w = unicodedata.normalize('NFD', w.lower())
    w = ''.join(c for c in w if 'a' <= c <= 'z')
    for a, b in (('ch', 'k'), ('sh', 's'), ('tz', 's'), ('ts', 's'), ('th', 't'), ('ph', 'p'), ('kh', 'k')):
        w = w.replace(a, b)
    w = w.translate(str.maketrans('vcqzfwj', 'bkkspbi'))
    w = re.sub(r'[aeiouyh]', '', w)
    w = re.sub(r'(.)\1+', r'\1', w)
    return w


def he_skels(line):
    """{skeleton: where in the line it first stands, 0…1}"""
    ws = uro().romanize_string(line, lcode='heb').split()
    out = {}
    for m, x in enumerate(ws):
        k = skel(x)
        if len(k) >= 3 and k not in out:
            out[k] = m / max(1, len(ws))
    return out


WORD = re.compile(r"[\wÀ-ÿ']+")


def is_anchor(w):
    bare = unicodedata.normalize('NFD', w.lower())
    bare = ''.join(c for c in bare if 'a' <= c <= 'z')
    return len(bare) >= 4 and bare not in STOP and (w[0].isupper() or "'" in w) and len(skel(w)) >= 3


def lags(HS, tr):
    """[(line, word index in line, lag, hebrew line, where in the Hebrew line 0…1)]"""
    out = []
    for i, line in enumerate(tr):
        for k, w in enumerate(line.split()):
            m = WORD.search(w)
            if not m or not is_anchor(m.group(0)):
                continue
            a = skel(m.group(0))
            js = [j for j in range(max(0, i - R), min(len(HS), i + R + 1)) if a in HS[j]]
            # only a word said once nearby proves anything: "Rabino" said five times in a row matched the
            # wrong one and showed aligned lessons 13 lines off (2026-10-21, FmM8o31AzOc)
            if len(js) == 1:
                j = js[0]
                out.append((i, k, i - j, j, HS[j][a]))
    return out


def stretches(L, n):
    """line ranges whose rolling lag (median of 9 anchors) reaches DRIFT, widened by 12 and merged"""
    out = []
    for x in range(len(L)):
        win = [d for _, _, d, _, _ in L[max(0, x - 4): x + 5]]
        if len(win) >= 5 and abs(statistics.median(win)) >= DRIFT:
            s, e = max(0, L[x][0] - 12), min(n - 1, L[x][0] + 12)
            if out and s <= out[-1][1] + 1:
                out[-1][1] = max(out[-1][1], e)
            else:
                out.append([s, e])
    return out


def report(vid, lang, HS, tr):
    L = lags(HS, tr)
    n = len(tr)
    wins = []
    for s in range(0, n, 60):
        w = [d for i, _, d, _, _ in L if s <= i < s + 60]
        if w:
            wins.append([s, round(statistics.median(w), 1), len(w)])
    st = stretches(L, n)
    worst = max([abs(w[1]) for w in wins if w[2] >= 3] or [0])
    return {'lines': n, 'anchors': len(L), 'windows': wins, 'stretches': st, 'worst': worst}, L


# ── repair ───────────────────────────────────────────────────────────────────────────────────────
def lis(points):
    """longest strictly increasing run of (word position, hebrew line) by both coordinates"""
    tails, prev, idx = [], [None] * len(points), []
    for n, (_, j) in enumerate(points):
        k = bisect.bisect_left(tails, j)
        if k == len(tails):
            tails.append(j)
            idx.append(n)
        else:
            tails[k] = j
            idx[k] = n
        prev[n] = idx[k - 1] if k else None
    out, n = [], idx[-1] if idx else None
    while n is not None:
        out.append(points[n])
        n = prev[n]
    return out[::-1]


PUNCT = re.compile(r'[.!?;:,»"”)]$')


def resplit(tr, he, L, s, e):
    """new texts for lines s..e of tr (their words re-cut on the Hebrew lines)"""
    words, starts = [], []
    for i in range(s, e + 1):
        starts.append(len(words))
        words.extend(tr[i].split())
    if not words:
        return None
    # pins: the word where each anchor's Hebrew line should start — the anchor's position minus its share
    # of the line before it (where the name stands in the Hebrew line × the line's expected word count)
    wlen0 = [max(1, len(h)) for h in he]
    per = len(words) / max(1, sum(wlen0[s:e + 1]))
    pins = sorted({(max(1, starts[i - s] + k - round(f * wlen0[j] * per)), j) for i, k, _, j, f in L if s <= i <= e and s < j <= e})
    pins = lis(pins)
    # the stretch's own edges: its first word starts line s, everything ends at line e
    fixed = [(0, s)] + [(p, j) for p, j in pins if p > 0] + [(len(words), e + 1)]
    wlen = [max(1, len(h)) for h in he]
    cut = {s: 0}
    for (p0, j0), (p1, j1) in zip(fixed, fixed[1:]):
        if j1 <= j0:
            continue
        span = p1 - p0
        tot = sum(wlen[j] for j in range(j0, j1))
        acc = 0
        for j in range(j0 + 1, j1):
            acc += wlen[j - 1]
            c = p0 + round(span * acc / tot)
            # move the cut to the nearest punctuation within 3 words
            for d in (0, 1, -1, 2, -2, 3, -3):
                q = c + d
                if p0 < q < p1 and PUNCT.search(words[q - 1]):
                    c = q
                    break
            cut[j] = max(cut.get(j - 1, p0), min(c, p1))
        cut[j1] = p1
    out = []
    for j in range(s, e + 1):
        a = cut.get(j, cut.get(j - 1, 0))
        b = cut.get(j + 1, len(words))
        out.append(' '.join(words[a:b]))
    return out


def aligned(HS, tr, s, e):
    """how many anchors of lines s..e sit on their own Hebrew line (±1)"""
    return sum(1 for i, _, d, _, _ in lags(HS, tr) if s <= i <= e and abs(d) <= 1)


def safe(he, old, new, HS, s, e):
    """a re-cut stretch is kept only if no Hebrew line lost its translation, no line swelled, and more
    names now sit on their own line (2026-10-21: the first run trusted the drift score alone and emptied
    lines 392–403 of nEeDpt7qtTI — all 78 repairs were put back)"""
    ratio = sum(len(x) for x in old) / max(1, sum(len(x) for x in he))
    for j in range(s, e + 1):
        hw = len(he[j].split())
        if hw >= 3 and not new[j].strip():
            return False, f'line {j} emptied'
        if len(new[j]) > 3 * ratio * len(he[j]) + 50:
            return False, f'line {j} swelled'
    before, after = aligned(HS, old, s, e), aligned(HS, new, s, e)
    if after <= before:
        return False, f'names on their line {before} → {after}'
    return True, ''


# ── main ─────────────────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['measure', 'repair'])
    ap.add_argument('--lane', type=int, default=1)
    ap.add_argument('--lanes', type=int, default=1)
    ap.add_argument('--ids-file', default='data/drift-ids.txt')
    ap.add_argument('--ids', default='')
    ap.add_argument('--langs', default='pt,en')
    ap.add_argument('--out', default='out/drift')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    ids = [x for x in a.ids.split(',') if x] or [l.strip() for l in open(a.ids_file, encoding='utf8') if l.strip()]
    ids = [v for v in ids if a.ids or lane_of(v, a.lanes) == a.lane - 1]
    os.makedirs(a.out, exist_ok=True)
    print(f'{a.mode} lane {a.lane}/{a.lanes}: {len(ids)} lessons', flush=True)
    rep = {}
    for vid in ids:
        try:
            doc = kv_get(f'videos/transcript/{vid}')
            if not doc or not doc.get('cues'):
                continue
            he = [c[2] for c in doc['cues']]
            HS = [he_skels(x) for x in he]
            rep[vid] = {}
            for lang in a.langs.split(','):
                tdoc = kv_get(f'videos/transcript/{vid}/{lang}')
                tr = [x or '' for x in (tdoc or {}).get('texts') or []]
                if len(tr) != len(he):
                    continue
                r, L = report(vid, lang, HS, tr)
                if a.mode == 'repair' and r['stretches']:
                    new = list(tr)
                    took = []
                    for s, e in r['stretches']:
                        got = resplit(new, he, L, s, e)
                        if not got:
                            continue
                        cand = new[:s] + got + new[e + 1:]
                        ok, why = safe(he, tr, cand, HS, s, e)
                        if ok:
                            new = cand
                            took.append([s, e])
                        else:
                            r.setdefault('refused', []).append([s, e, why])
                    r2, _ = report(vid, lang, HS, new)
                    better = bool(took)
                    r['after'] = {'worst': r2['worst'], 'stretches': r2['stretches'], 'took': took, 'applied': better and not a.dry}
                    if better and not a.dry:
                        if not kv_get(f'videos/transcript/{vid}/{lang}/before-drift'):
                            kv_put(f'videos/transcript/{vid}/{lang}/before-drift', tdoc)
                        kv_put(f'videos/transcript/{vid}/{lang}', {**tdoc, 'texts': new, 'drift': {'repaired': time.strftime('%Y-%m-%d'), 'worst_before': r['worst'], 'worst_after': r2['worst']}})
                rep[vid][lang] = r
                tag = f"worst {r['worst']:+.1f}, {len(r['stretches'])} stretches"
                if 'after' in r:
                    tag += f" → worst {r['after']['worst']:+.1f}{' ✓' if r['after']['applied'] else (' (dry)' if a.dry else ' (kept the old)')}"
                print(f'{vid} {lang}: {tag}', flush=True)
        except Exception as ex:  # one lesson must not stop the lane
            print(f'{vid}: ✗ {str(ex)[:140]}', flush=True)
    json.dump(rep, open(f'{a.out}/{a.mode}-{a.lane}.json', 'w', encoding='utf8'), ensure_ascii=False)
    print('done', flush=True)


if __name__ == '__main__':
    sys.exit(main())
