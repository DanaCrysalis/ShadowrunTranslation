#!/usr/bin/env python3
"""
preview.py -- render a block exactly as the sub CPU will draw it.

This reads the PATCHED bytes, not the translation source, so what you see is
what the renderer will build. Both glyph paths are reproduced from §5:

  full-width  value & $7FFF -> 16x14 glyph from the KANJI bank
  half-width  two glyphs, high byte then low byte, each `byte * 16` into
              FONT86, 8x16

One source word is one 16px cell either way (§5.3), so the cell grid is the
same for both. Window width is the widest line's cell count, which is what the
sub CPU writes to $08000A for the main CPU to size its DMA from (§6.1) -- so
the frame drawn here is the window the game will actually open.

  python3 preview.py ADV_01_reflow.D out.png 0x3916 [0x3958 ...]
"""
import struct
import sys

from PIL import Image, ImageDraw

CELL = 16
FW_LO, FW_HI = 0x8000, 0x9A00
NEWLINE = 0x0D0A
SCALE = 3
INK = (232, 232, 240)
BG = (16, 18, 28)
FRAME = (96, 132, 200)

_atlas = None


def fw_glyph(i):
    """16x14 full-width glyph, recovered from kanji1_atlas.png."""
    global _atlas
    if _atlas is None:
        from atlasx import glyph
        _atlas = glyph
    return _atlas(i)


def hw_rows(font, b):
    return font[b * 16:(b + 1) * 16]


def block_lines(data, off):
    from blockpatch import block_words
    n = block_words(data, off)
    lines, cur = [], []
    for k in range(n):
        v = struct.unpack_from('>H', data, off + 2 * k)[0]
        if v == NEWLINE:
            lines.append(cur)
            cur = []
        else:
            cur.append(v)
    if cur:
        lines.append(cur)
    return lines


def render(data, font, offs):
    blocks = [(o, block_lines(data, o)) for o in offs]
    w = max(max((len(l) for l in ls), default=1) for _, ls in blocks)
    h = sum(len(ls) for _, ls in blocks) + len(blocks) - 1
    im = Image.new('RGB', (w * CELL + 8, h * CELL + 8), BG)
    px = im.load()
    y0 = 4
    for bi, (off, ls) in enumerate(blocks):
        bw = max((len(l) for l in ls), default=1)
        d = ImageDraw.Draw(im)
        d.rectangle([2, y0 - 2, bw * CELL + 5, y0 + len(ls) * CELL + 1],
                    outline=FRAME)
        for r, line in enumerate(ls):
            for c, v in enumerate(line):
                x = 4 + c * CELL
                y = y0 + r * CELL
                if FW_LO <= v < FW_HI:
                    for gy, row in enumerate(fw_glyph(v & 0x7FFF)):
                        for gx in range(16):
                            if (row >> (15 - gx)) & 1:
                                px[x + gx, y + gy + 1] = INK
                else:
                    for half, b in enumerate((v >> 8, v & 0xFF)):
                        rows = hw_rows(font, b)
                        for gy, row in enumerate(rows):
                            for gx in range(8):
                                if (row >> (7 - gx)) & 1:
                                    px[x + half * 8 + gx, y + gy] = INK
        y0 += (len(ls) + 1) * CELL
    return im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)


def main():
    src, out = sys.argv[1], sys.argv[2]
    offs = [int(a, 16) for a in sys.argv[3:]]
    data = open(src, 'rb').read()
    import os
    font = open(os.environ.get('FONT86', 'FONT86_en.G'), 'rb').read()
    im = render(data, font, offs)
    im.save(out)
    for o in offs:
        ls = block_lines(data, o)
        print('0x%06X  %d lines, widest %d cells -> window %d x %d'
              % (o, len(ls), max(len(l) for l in ls),
                 max(len(l) for l in ls), len(ls)))
    print('%s written' % out)


if __name__ == '__main__':
    main()
