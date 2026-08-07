#!/usr/bin/env python3
"""
hifont.py -- mirror FONT86's ASCII glyphs into the high half of the font.

The main-CPU script interpreter (SRUN_X.P $1342) classifies a word as text
with BMI -- the SIGN BIT, not the $8000-$99FF window. So a half-width pair
like $5361 ("Sa") is bit-15 clear, falls into the control-code dispatcher,
matches nothing, and is silently consumed. The sub CPU still draws it, but the
main CPU's cursor never advances, so the window geometry and DMA extent are
computed as though those cells did not exist.

Encoding each Latin byte as (ASCII | $80) puts every pair at >= $A0A0, which:
  * is negative, so the main CPU takes the TEXT path
  * is >= $9A00, so the sub CPU takes the HALF-WIDTH path
  * masks to slot (ASCII | $80) in FONT86
  * can never produce the reserved high bytes $0D/$21/$23/$24/$63

So the only thing needed is glyphs at $A0-$FE. This copies them there.
That displaces the half-width katakana, which an English patch replaces anyway.

  python3 hifont.py FONT86_en.G FONT86_hi.G
"""
import sys
src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
assert len(d) == 4096, len(d)
n = 0
for c in range(0x20, 0x7F):
    hi = c + 0x80
    d[hi*16:(hi+1)*16] = d[c*16:(c+1)*16]
    n += 1
open(dst, 'wb').write(bytes(d))
print('%s: %d glyphs mirrored $20-$7E -> $A0-$FE' % (dst, n))
