"""Recover 16x14 glyph bitmaps from kanji1_atlas.png.

The atlas is written by srtext.py at 2x NEAREST with no compression, so the
original bitmaps come back exactly -- which makes it a usable stand-in for
KANJI1.K when the bank itself isn't to hand.

Layout (from srtext.py cmd_atlas): cell 18x26, glyph pasted at (x+1, y+10),
32 columns, whole image resized 2x.
"""
import os

from PIL import Image

def _find_atlas():
    if os.environ.get('KANJI_ATLAS'):
        return os.environ['KANJI_ATLAS']
    here = os.path.dirname(os.path.abspath(__file__))
    for c in ('kanji1_atlas.png',
              os.path.join(here, 'kanji1_atlas.png'),
              os.path.join(here, '..', 'reference', 'kanji1_atlas.png'),
              os.path.join('reference', 'kanji1_atlas.png')):
        if os.path.exists(c):
            return c
    return 'kanji1_atlas.png'


ATLAS = _find_atlas()
_im = None


def _img():
    global _im
    if _im is None:
        _im = Image.open(ATLAS).convert('L')
    return _im


def glyph(i):
    """Glyph i as 14 rows of 16 bits, MSB = leftmost pixel."""
    im = _img()
    x0 = ((i % 32) * 18 + 1) * 2
    y0 = ((i // 32) * 26 + 10) * 2
    out = []
    for y in range(14):
        r = 0
        for x in range(16):
            if im.getpixel((x0 + x * 2, y0 + y * 2)) < 128:
                r |= 1 << (15 - x)
        out.append(r)
    return out


def bbox(g):
    """(x0, y0, x1, y1) of the ink, or None if the glyph is blank."""
    ys = [y for y, r in enumerate(g) if r]
    if not ys:
        return None
    xs = [x for x in range(16) if any((r >> (15 - x)) & 1 for r in g)]
    return min(xs), min(ys), max(xs), max(ys)
