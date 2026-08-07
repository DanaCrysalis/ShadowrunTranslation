#!/usr/bin/env python3
"""
priority.py -- merge every independent check into one hand-check list.

Four oracles, none of which depends on how often a glyph appears:

  freq    occurrences in ADV_01.D. Weak on its own (findings §8.1) but a
          glyph used 200 times in readable sentences is not wrong.
  pixel   rank of the claimed character when the real bitmap is correlated
          against renders of all 717 claimed characters (verify_glyphs.py).
  sort    for kanji: does the claimed character fit the bank's on-reading
          sort between its neighbours? (findings §10.2)
  kana    for kana: small/large ink size against the paired counterpart.

An index is CONFIRMED if any strong oracle fires. It goes on the hand-check
list only when every oracle is silent or negative.

Usage: python3 priority.py > handcheck.txt
"""
import sys

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tables'))
try:
    import kanji1_table_v2 as K
except ImportError:
    import kanji1_table as K
from collate import key

CHARS = K.CHARS
SMALL = set('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ')


def load_counts(p='counts.tsv'):
    d = {}
    for ln in open(p).read().splitlines()[1:]:
        a, b = ln.split('\t')
        d[int(a)] = int(b)
    return d


def load_pixel(p='glyph_verify.tsv'):
    d = {}
    for ln in open(p, encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t')
        if len(c) >= 4 and c[2] and c[3]:
            d[int(c[0])] = (int(c[2]), float(c[3]), c[4] if len(c) > 4 else '')
    return d


def kanji_sort_ok():
    """Indices whose claimed reading fits the on-reading sort."""
    from pykakasi.kanji import Kanwa
    kw = Kanwa()
    extra = {'\u53e9': ['\u305f\u305f\u304f'],      # 叩 -> たたく (kun-sorted)
             '\u623b': ['\u3082\u3069\u308b']}      # 戻 -> もどる (kun-sorted)
    rd = {}
    for i in range(163, len(CHARS)):
        c = CHARS[i]
        try:
            rs = {r[0] for r in (kw.load(c).get(c) or []) if r[0]}
        except Exception:
            rs = set()
        rs |= set(extra.get(c, []))
        rd[i] = sorted(rs, key=key)
    ok = {}
    prev = key('')
    for i in range(163, len(CHARS)):
        rs = rd[i]
        if not rs:
            ok[i] = None
            continue
        fit = [r for r in rs if key(r) >= prev]
        ok[i] = bool(fit)
        prev = min(key(r) for r in (fit or rs))
    return ok


def kana_size_ok():
    """Pair each small kana with its large counterpart and compare ink."""
    from atlasx import glyph, bbox
    pair = dict(zip('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ',
                    'あいうえおつやゆよわアイウエオツヤユヨワ'))
    idx = {c: i for i, c in enumerate(CHARS)}
    res = {}
    for i in range(26, 163):
        c = CHARS[i]
        big = pair.get(c)
        if big is None or big not in idx:
            res[i] = None
            continue
        a, b = bbox(glyph(i)), bbox(glyph(idx[big]))
        if not a or not b:
            res[i] = None
            continue
        ha, hb = a[3] - a[1] + 1, b[3] - b[1] + 1
        res[i] = ha < hb
    return res


def main():
    cnt = load_counts()
    px = load_pixel()
    ks = kanji_sort_ok()
    kz = kana_size_ok()

    rows = []
    for i in range(len(CHARS)):
        c = CHARS[i]
        n = cnt.get(i, 0)
        rank, sc, top = px.get(i, (None, None, ''))
        ev = []
        if n >= 20:
            ev.append('freq(%d)' % n)
        if rank == 1:
            ev.append('pixel')
        elif rank and rank <= 3:
            ev.append('pixel~%d' % rank)
        if ks.get(i):
            ev.append('sort')
        if kz.get(i):
            ev.append('kana-size')
        if 26 <= i < 163:
            ev.append('kana-sort')   # run is strictly monotonic, 0 violations
        if 11 <= i < 21:
            ev.append('digit-run')
        rows.append((i, c, n, rank, sc, top, ev))

    conf = [r for r in rows if r[6]]
    unconf = [r for r in rows if not r[6]]

    print('KANJI1.K table -- evidence summary (%d entries)\n' % len(CHARS))
    print('  confirmed by at least one oracle : %d' % len(conf))
    print('  no oracle fired                  : %d' % len(unconf))
    print()
    weak = [r for r in rows if r[3] and r[3] > 3 and 'pixel' not in
            ' '.join(r[6])]
    print('PIXEL-WEAK BUT POSITION-CONFIRMED -- %d indices' % len(weak))
    print('(these sit inside a sort-verified run, so position is pinned; the')
    print(' bitmap correlation just cannot resolve them at 16x14. Glance only.)\n')
    print('%-6s %-4s %-6s %-6s %-7s %s'
          % ('index', 'char', 'count', 'rank', 'score', 'pixel top-5'))
    print('-' * 62)
    for i, c, n, rank, sc, top, ev in sorted(weak, key=lambda r: (r[2], r[0])):
        print('%-6d %-4s %-6d %-6s %-7s %s'
              % (i, c, n, rank, '%.3f' % sc, top))
    print()
    print('HAND-CHECK LIST -- %d indices, in priority order' % len(unconf))
    print('(sorted by occurrence count ascending: rarest first, since a rare')
    print(' glyph is also the one a wrong reading will hide in)\n')
    print('%-6s %-4s %-6s %-6s %-7s %s'
          % ('index', 'char', 'count', 'rank', 'score', 'pixel top-5'))
    print('-' * 62)
    for i, c, n, rank, sc, top, ev in sorted(unconf, key=lambda r: (r[2], r[0])):
        print('%-6d %-4s %-6d %-6s %-7s %s'
              % (i, c, n, rank if rank else '-',
                 ('%.3f' % sc) if sc is not None else '-', top))


if __name__ == '__main__':
    main()
