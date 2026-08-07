#!/usr/bin/env python3
"""
verify_glyphs.py -- check every entry of the KANJI1.K table by rendering the
claimed character and comparing it to the real glyph bitmap.

The point is to replace "hand-check the 392 rare indices" with "hand-check the
handful the machine can't confirm". For each index i:

  * take the real 16x14 glyph from kanji1_atlas.png
  * render every character claimed anywhere in the table with a Japanese font
  * normalise both to their ink bounding box and resample to a common grid
  * rank all candidates by similarity

If CHARS[i] comes out rank 1, the identification is confirmed by pixels, which
is an oracle that does not care whether the glyph appears once or a thousand
times. If it does not, the index goes on the hand-check list along with what
the machine thought it looked like instead.

Usage: python3 verify_glyphs.py [out.tsv]
"""
import sys

from PIL import Image, ImageDraw, ImageFont

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tables'))
try:
    import kanji1_table_v2 as K
except ImportError:
    import kanji1_table as K
from atlasx import glyph, bbox

FONT = '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf'
GRID = 16          # normalised comparison grid
CHARS = K.CHARS


def norm(mask, w, h):
    """Crop a boolean mask to its ink bbox and resample to GRID x GRID."""
    xs = [x for x in range(w) if any(mask[y][x] for y in range(h))]
    ys = [y for y in range(h) if any(mask[y])]
    if not xs or not ys:
        return None
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    im = Image.new('L', (x1 - x0 + 1, y1 - y0 + 1))
    px = im.load()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px[x - x0, y - y0] = 255 if mask[y][x] else 0
    im = im.resize((GRID, GRID), Image.BILINEAR)
    return list(im.getdata())


def atlas_mask(i):
    g = glyph(i)
    return [[bool((r >> (15 - x)) & 1) for x in range(16)] for r in g]


def render_mask(ch, font, size=48):
    im = Image.new('L', (size * 2, size * 2), 0)
    ImageDraw.Draw(im).text((size // 2, size // 4), ch, fill=255, font=font)
    px = im.load()
    return [[px[x, y] > 100 for x in range(size * 2)] for y in range(size * 2)], size * 2


def score(a, b):
    """Normalised correlation of two GRID*GRID greyscale vectors."""
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    va = sum((x - ma) ** 2 for x in a) ** .5
    vb = sum((x - mb) ** 2 for x in b) ** .5
    if va == 0 or vb == 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'glyph_verify.tsv'
    font = ImageFont.truetype(FONT, 48)

    # render every distinct claimed character once
    pool = sorted(set(CHARS))
    tmpl = {}
    for ch in pool:
        if ch == '\u3000':
            continue
        m, w = render_mask(ch, font)
        v = norm(m, w, w)
        if v:
            tmpl[ch] = v
    print('%d templates rendered' % len(tmpl))

    rows = []
    for i in range(len(CHARS)):
        want = CHARS[i]
        v = norm(atlas_mask(i), 16, 14)
        if v is None or want not in tmpl:
            rows.append((i, want, None, None, None))
            continue
        ranked = sorted(((score(v, t), c) for c, t in tmpl.items()),
                        reverse=True)
        best_s, best_c = ranked[0]
        rank = next(k for k, (s, c) in enumerate(ranked) if c == want) + 1
        rows.append((i, want, rank, round(ranked[rank - 1][0], 3),
                     ''.join(c for _, c in ranked[:5])))
        if i % 100 == 0:
            print('  ... %d' % i, flush=True)

    with open(out, 'w', encoding='utf-8') as f:
        f.write('index\tchar\trank\tscore\ttop5\n')
        for i, ch, rank, s, top in rows:
            f.write('%d\t%s\t%s\t%s\t%s\n'
                    % (i, ch, rank if rank else '', s if s else '', top or ''))

    ok = [r for r in rows if r[2] == 1]
    top3 = [r for r in rows if r[2] and r[2] <= 3]
    bad = [r for r in rows if r[2] and r[2] > 3]
    print('\nrank 1 (pixel-confirmed) : %d' % len(ok))
    print('rank 2-3                 : %d' % (len(top3) - len(ok)))
    print('rank >3 (needs eyes)     : %d' % len(bad))
    print('\nworst 40:')
    for i, ch, rank, s, top in sorted(bad, key=lambda r: -r[2])[:40]:
        print('  %3d claimed %s  rank %3d  score %.3f  looks like: %s'
              % (i, ch, rank, s, top))


if __name__ == '__main__':
    main()
