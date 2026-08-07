#!/usr/bin/env python3
"""
audit_table.py -- independent checks on the KANJI1.K character table.

Frequency is a weak oracle: findings §8.1 notes index 98 survived because it
occurs twice, and "reads plausibly in every context" is no filter at n=2. 183
indices in ADV_01.D occur exactly once. So this checks STRUCTURE instead, which
does not care how often a glyph appears:

  1. KANA SORT      indices 26-162 must be strictly increasing in Unicode
                    order (the Unicode kana blocks are gojuon order, with
                    small-before-large and dakuten interleaved, which is
                    exactly the bank's sort per findings §10.2).
  2. KANA SIZE      small kana (ぁ ァ ゃ ッ ...) have visibly smaller ink than
                    their large counterparts. Measured from the atlas bitmaps,
                    not eyeballed.
  3. KANJI SORT     indices 163-716 are sorted by on-reading. For each kanji,
                    take its full reading set and try to pick one reading per
                    index so the whole run is non-decreasing. If that succeeds,
                    every kanji is consistent with its neighbours -- which is
                    an oracle completely independent of how rare it is.
  4. DUPLICATES     no character should be claimed twice; no two indices
                    should share a bitmap.
  5. FREQUENCY      list indices occurring < N times, for hand-checking.

Usage:  python3 audit_table.py [counts.tsv]
"""
import sys
from collections import defaultdict

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tables'))
try:
    import kanji1_table_v2 as K
except ImportError:
    import kanji1_table as K
from atlasx import glyph, bbox

CHARS = K.CHARS
HIRA = range(26, 98)
KATA = range(98, 163)
KANJI = range(163, len(CHARS))

SMALL = set('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ')


def hdr(t):
    print('\n' + '=' * 68 + '\n' + t + '\n' + '=' * 68)


# ------------------------------------------------------------------ 1. sort
def check_kana_sort():
    hdr('1. KANA SORT ORDER (must be strictly increasing in Unicode order)')
    bad = 0
    for name, rng in (('hiragana', HIRA), ('katakana', KATA)):
        prev = None
        for i in rng:
            c = CHARS[i]
            if prev is not None and ord(c) <= ord(prev[1]):
                print('  VIOLATION %s: index %d %r follows index %d %r'
                      % (name, i, c, prev[0], prev[1]))
                bad += 1
            prev = (i, c)
        print('  %-9s %d..%d  checked' % (name, rng.start, rng.stop - 1))
    print('  -> %d violations' % bad)
    return bad


# ------------------------------------------------------------------ 2. size
def check_kana_size():
    hdr('2. KANA INK SIZE (small kana must measure smaller than large kana)')
    rows = []
    for i in list(HIRA) + list(KATA):
        bb = bbox(glyph(i))
        if bb is None:
            rows.append((i, CHARS[i], None, None))
            continue
        h = bb[3] - bb[1] + 1
        w = bb[2] - bb[0] + 1
        rows.append((i, CHARS[i], h, w))
    big = [r for r in rows if r[1] not in SMALL and r[2]]
    sml = [r for r in rows if r[1] in SMALL and r[2]]
    if big:
        print('  large kana: n=%d  mean ink height %.1f  min %d'
              % (len(big), sum(r[2] for r in big) / len(big),
                 min(r[2] for r in big)))
    if sml:
        print('  small kana: n=%d  mean ink height %.1f  max %d'
              % (len(sml), sum(r[2] for r in sml) / len(sml),
                 max(r[2] for r in sml)))
    thr = 11
    print('  threshold: ink height >= %d => large\n' % thr)
    bad = 0
    for i, c, h, w in rows:
        if h is None:
            continue
        claimed_small = c in SMALL
        looks_small = h < thr
        if claimed_small != looks_small:
            print('  MISMATCH index %3d claimed %r (%s) but ink height %d (%s)'
                  % (i, c, 'small' if claimed_small else 'large', h,
                     'small' if looks_small else 'large'))
            bad += 1
    print('  -> %d mismatches' % bad)
    return bad


# ----------------------------------------------------------------- 3. kanji
def readings():
    from pykakasi.kanji import Kanwa
    kw = Kanwa()
    out = {}
    for i in KANJI:
        c = CHARS[i]
        try:
            rs = kw.load(c).get(c) or []
        except Exception:
            rs = []
        out[i] = sorted({r[0] for r in rs if r[0]})
    return out


def check_kanji_sort():
    hdr('3. KANJI ON-READING SORT (findings §10.2: sorted by on-reading)')
    rd = readings()
    nomatch = [i for i in KANJI if not rd[i]]
    if nomatch:
        print('  no readings available for %d indices: %s'
              % (len(nomatch), [CHARS[i] for i in nomatch]))
    prev = ''
    viol = []
    for i in KANJI:
        rs = rd[i]
        if not rs:
            continue
        ok = [r for r in rs if r >= prev]
        if ok:
            prev = min(ok)
        else:
            viol.append((i, CHARS[i], rs, prev))
            prev = min(rs)
    print('  %d of %d kanji fit a single non-decreasing reading assignment'
          % (len(list(KANJI)) - len(viol) - len(nomatch), len(list(KANJI))))
    if viol:
        print('\n  %d indices could not be placed in order:' % len(viol))
        for i, c, rs, p in viol:
            print('    index %3d  %s  readings=%s  (previous key %r)'
                  % (i, c, '/'.join(rs), p))
    return viol


# ------------------------------------------------------------- 4. duplicates
def check_dupes():
    hdr('4. DUPLICATES')
    bad = 0
    seen = defaultdict(list)
    for i, c in enumerate(CHARS):
        seen[c].append(i)
    for c, ix in seen.items():
        if len(ix) > 1:
            print('  character %r claimed at indices %s' % (c, ix))
            bad += 1
    bm = defaultdict(list)
    for i in range(len(CHARS)):
        g = tuple(glyph(i))
        if any(g):
            bm[g].append(i)
    for g, ix in bm.items():
        if len(ix) > 1:
            print('  identical bitmaps at indices %s (%s)'
                  % (ix, ''.join(CHARS[i] for i in ix)))
            bad += 1
    print('  -> %d duplicate issues' % bad)
    return bad


# -------------------------------------------------------------- 5. frequency
def check_freq(counts_path, n=5):
    hdr('5. LOW-FREQUENCY INDICES (weakest contextual evidence)')
    cnt = {}
    for ln in open(counts_path).read().splitlines()[1:]:
        a, b = ln.split('\t')
        cnt[int(a)] = int(b)
    unused = [i for i in range(len(CHARS)) if i not in cnt]
    rare = sorted((c, i) for i, c in cnt.items() if c < n)
    print('  never used in ADV_01.D : %d indices' % len(unused))
    for k in range(1, n):
        m = [i for i, c in cnt.items() if c == k]
        print('  occurring %dx            : %d indices' % (k, len(m)))
    print('  total below %dx          : %d' % (n, len(rare)))
    return rare, unused


def main():
    counts = sys.argv[1] if len(sys.argv) > 1 else 'counts.tsv'
    check_kana_sort()
    check_kana_size()
    check_kanji_sort()
    check_dupes()
    check_freq(counts)


if __name__ == '__main__':
    main()
