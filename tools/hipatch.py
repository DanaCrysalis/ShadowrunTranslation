#!/usr/bin/env python3
"""
hipatch.py -- write English into dialogue using the HIGH-BIT encoding.

Same TSV as tailpatch.py (offset<TAB>keep<TAB>text) but every character is
emitted as (ASCII | $80), so the word lands at >= $A0A0 and the main-CPU
interpreter accepts it as text. Requires a font built by hifont.py.

There are no reserved characters in this encoding.
"""
import struct, sys
NEWLINE = 0x0D0A
def line_cells(data, off):
    n, p = 0, off
    while p < len(data)-1:
        if struct.unpack_from('>H', data, p)[0] == NEWLINE: return n
        n += 1; p += 2
    raise ValueError('no $0D0A after 0x%06X' % off)
def main():
    src, dst, spec = sys.argv[1:4]
    data = bytearray(open(src,'rb').read()); orig = bytes(data)
    for raw in open(spec, encoding='utf-8'):
        s = raw.rstrip('\n').rstrip('\r')
        if not s or s.startswith('#'): continue
        off_s, keep_s, text = s.split('\t')
        off, keep = int(off_s,16), int(keep_s)
        cells = line_cells(orig, off)
        if len(text) % 2: text += ' '
        room = (cells-keep)*2
        if len(text) > room:
            raise SystemExit('0x%06X: %d cells, keeping %d -> max %d chars, got %d'
                             % (off, cells, keep, room, len(text)))
        for k in range(0, len(text), 2):
            a, b = ord(text[k]), ord(text[k+1])
            if not (0x20 <= a <= 0x7E and 0x20 <= b <= 0x7E):
                raise SystemExit('non-printable-ASCII in %r' % text)
            w = ((a | 0x80) << 8) | (b | 0x80)
            assert w >= 0xA0A0
            struct.pack_into('>H', data, off + 2*(keep + k//2), w)
        print('0x%06X  %2d cells: %d original + %d English  %r'
              % (off, cells, keep, len(text)//2, text))
    assert len(data) == len(orig)
    open(dst,'wb').write(bytes(data))
    print('\n%s: %d bytes differ, length unchanged (%d)'
          % (dst, sum(1 for x,y in zip(orig,data) if x!=y), len(data)))
main()
