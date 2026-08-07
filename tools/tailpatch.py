#!/usr/bin/env python3
"""
tailpatch.py -- keep the first N original cells of a line, put ASCII in the rest.

Built to answer one question: when a dialogue block fails to draw, does the
sub CPU's draw loop TERMINATE at the first half-width word, or does the whole
block get rejected?

hwpatch.py writes English from the start of a line and leaves the tail as
original glyphs. This does the opposite -- original glyphs first, English
after -- which puts the suspect word in the middle of a line instead of at its
head. If the loop terminates on it, the window still draws, just truncated to
exactly the cells before the English. That truncation point is the measurement.

  python3 tailpatch.py in.D out.D spec.tsv

spec.tsv:  offset<TAB>keep<TAB>text
  offset = hex, start of the LINE (not the block)
  keep   = how many original cells to leave untouched at the line's head
  text   = ASCII, even length, at most (cells - keep) * 2 characters. Anything
           it does not fill stays as the original glyphs, so half-width can be
           placed in the MIDDLE of a line with original text on both sides.

Line length, block length and file length are all unchanged.
"""
import struct
import sys

NEWLINE = 0x0D0A


def line_cells(data, off):
    n, p = 0, off
    while p < len(data) - 1:
        if struct.unpack_from('>H', data, p)[0] == NEWLINE:
            return n
        n += 1
        p += 2
    raise ValueError('no $0D0A after 0x%06X' % off)


def main():
    src, dst, spec = sys.argv[1:4]
    data = bytearray(open(src, 'rb').read())
    orig = bytes(data)
    for raw in open(spec, encoding='utf-8'):
        s = raw.rstrip('\n').rstrip('\r')
        if not s or s.startswith('#'):
            continue
        off_s, keep_s, text = s.split('\t')
        off, keep = int(off_s, 16), int(keep_s)
        cells = line_cells(orig, off)
        room = (cells - keep) * 2
        if len(text) % 2:
            raise SystemExit('0x%06X: text must be an even number of characters '
                             '(one cell = two); got %d (%r)'
                             % (off, len(text), text))
        if len(text) > room:
            raise SystemExit('0x%06X: line is %d cells, keeping %d, so at most '
                             '%d chars fit; got %d (%r)'
                             % (off, cells, keep, room, len(text), text))
        for k in range(0, len(text), 2):
            hi, lo = ord(text[k]), ord(text[k + 1])
            w = (hi << 8) | lo
            if w == NEWLINE or 0x8000 <= w < 0x9A00 or hi in (0x21, 0x23, 0x24):
                raise SystemExit('reserved word $%04X from %r' % (w, text[k:k + 2]))
            struct.pack_into('>H', data, off + 2 * (keep + k // 2), w)
        used = len(text) // 2
        print('0x%06X  %2d cells: %d original + %d English + %d original  %r'
              % (off, cells, keep, used, cells - keep - used, text))
    assert len(data) == len(orig), 'LENGTH CHANGED -- do not use'
    open(dst, 'wb').write(bytes(data))
    print('\n%s: %d bytes differ, length unchanged (%d)'
          % (dst, sum(1 for a, b in zip(orig, data) if a != b), len(data)))


if __name__ == '__main__':
    main()
