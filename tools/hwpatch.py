#!/usr/bin/env python3
"""
hwpatch.py -- write half-width (Latin) text into a Shadowrun ADV_*.D file.

Model, from SRUN_S.PRG:
  A text block is  [line_count][word ...]$0D0A[word ...]$0D0A ...
  Each word is one CELL:
    $8000-$99FF -> one full-width glyph, KANJI bank at $054000
    anything else -> TWO half-width glyphs, FONT86.G at $05C000,
                     high byte then low byte, each index*16
  FONT86.G is indexed at true ASCII: 'A'=0x41, 'a'=0x61, '0'=0x30, ' '=0x20.

So: 1 original cell == 1 word == 2 Latin characters.
Keep the WORD COUNT of each line identical and the file length never changes,
which means no pointer, no offset and no line count has to be touched.

Usage:
  python3 hwpatch.py in.D out.D patch.tsv
  patch.tsv: offset<TAB>text[<TAB>cells]
             offset = hex, start of the line
             cells  = optional, how many cells to overwrite. Omit to take the
                      whole line; give a smaller number to leave the trailing
                      cells as their original full-width glyphs (mixed line).

Reserved values -- the tool refuses to emit them:
  $0D0A  newline
  $8000-$99FF  would be misread as a full-width glyph (impossible from ASCII)
  high byte $21, $23 or $24  -- $2323/$2424 are window control and $2100 is
  the show-portrait command, all consumed by the main-CPU script interpreter
  before the block reaches the sub CPU. A pair whose FIRST character is
  '!' (0x21), '#' (0x23) or '$' (0x24) is unsafe; pad so it lands second.
"""
import struct, sys

NEWLINE = 0x0D0A


def line_words(data, off):
    """Word count of the line starting at off (up to but not incl. $0D0A)."""
    n = 0
    p = off
    while p < len(data) - 1:
        if struct.unpack_from('>H', data, p)[0] == NEWLINE:
            return n
        n += 1
        p += 2
    raise ValueError('no $0D0A after 0x%06X' % off)


def encode(text, cells):
    """ASCII -> list of words, padded/checked to exactly `cells` words."""
    limit = cells * 2
    if len(text) > limit:
        raise ValueError('%r is %d chars, budget is %d' % (text, len(text), limit))
    t = text.ljust(limit, ' ')
    words = []
    for i in range(0, limit, 2):
        hi, lo = ord(t[i]), ord(t[i + 1])
        if hi > 0xFF or lo > 0xFF:
            raise ValueError('non-Latin-1 char in %r' % text)
        w = (hi << 8) | lo
        if w == NEWLINE or 0x8000 <= w < 0x9A00 or hi in (0x21, 0x23, 0x24):
            raise ValueError('reserved word $%04X from %r' % (w, t[i:i + 2]))
        words.append(w)
    return words


def patch(data, off, text, cells=None):
    avail = line_words(data, off)
    if cells is None:
        cells = avail
    if cells > avail:
        raise ValueError('line at 0x%06X has %d cells, asked for %d'
                         % (off, avail, cells))
    words = encode(text, cells)
    out = bytearray(data)
    for k, w in enumerate(words):
        struct.pack_into('>H', out, off + 2 * k, w)
    return bytes(out), cells


def main():
    src, dst, tsv = sys.argv[1], sys.argv[2], sys.argv[3]
    data = open(src, 'rb').read()
    n = 0
    for raw in open(tsv, encoding='utf-8'):
        raw = raw.rstrip('\n').rstrip('\r')
        if not raw or raw.startswith('#'):
            continue
        parts = raw.split('\t')
        off = int(parts[0], 16)
        text = parts[1] if len(parts) > 1 else ''
        want = int(parts[2]) if len(parts) > 2 and parts[2].strip() else None
        data, cells = patch(data, off, text, want)
        kept = line_words(data, off) - cells
        print('0x%06X  %d cells (%d chars)%s  %r'
              % (off, cells, cells * 2,
                 '  [+%d cells left as-is]' % kept if kept else '', text))
        n += 1
    open(dst, 'wb').write(data)
    orig = open(src, 'rb').read()
    assert len(data) == len(orig), 'LENGTH CHANGED -- do not use'
    diff = sum(1 for a, b in zip(orig, data) if a != b)
    print('\n%s: %d lines patched, %d bytes differ, length unchanged (%d)'
          % (dst, n, diff, len(data)))


if __name__ == '__main__':
    main()
