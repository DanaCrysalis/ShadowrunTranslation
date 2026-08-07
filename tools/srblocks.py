#!/usr/bin/env python3
"""
srblocks.py -- Shadowrun (Sega CD, JP) block-level script extractor.

Replaces srtext.py's parse(), which treated every sub-$8000 word as a string
terminator and therefore (a) threw away the half-width text that is genuinely
in the file and (b) chopped every block at its control run.

GRAMMAR (from findings §4, §6, verified against ADV_01.D word-for-word)
----------------------------------------------------------------------
The text region is a flat word stream. Every word is one screen CELL:

    $8000-$99FF   one full-width glyph, index = value & $7FFF
    $0D0A         end of line
    anything else two half-width glyphs, high byte then low byte

Control words are NOT part of that stream -- they are consumed by the main-CPU
script interpreter before the block reaches the sub CPU. They appear only at a
LINE START (immediately after a $0D0A, or at the very start of the region), and
form a run matching, in this fixed order, any non-empty subset of:

    WIN       $2323 | $2424            window / page control
    CNT       $0001-$001F              line-count header (menu-style blocks)
    PORTRAIT  $2100 <idword> <flagword>
    EXTRA     $63C8 | $63F8            uncatalogued, always run-tail

BLOCK TYPES
-----------
  count  a run containing CNT. Exactly CNT $0D0A-terminated lines follow.
         These are the menu / list blocks. Self-delimiting.
  page   a run with no CNT. Lines follow until the next control run.
         This is dialogue. Terminator-delimited, matching the third draw
         loop in SRUN_S.PRG which treats high bytes $23/$24 as terminators.

Commands
--------
  blocks   TEXT.D [table.tsv]        block listing -> stdout
  sheet    TEXT.D table.tsv out.tsv  translation worksheet, keyed by block
  counts   TEXT.D out.tsv            glyph index occurrence counts
  verify   TEXT.D                    prove every word in the region is claimed
"""
import os
import struct
import sys
from collections import Counter

NEWLINE = 0x0D0A
FW_LO, FW_HI = 0x8000, 0x9A00
WIN = (0x2323, 0x2424)
EXTRA = (0x63C8, 0x63F8)
PORTRAIT = 0x2100

# --------------------------------------------------------------- half-width
# FONT86.G is indexed at true ASCII / JIS X 0201. 0xA1-0xDF is exact JIS order;
# the voiced/semi-voiced forms are precomposed into otherwise-unused slots.
# The scattered slots below were recovered by bitmap-diffing FONT86.G against
# its own base katakana (see hwmap.py) -- they are not guesses.
JIS_KANA = ("\uff61\uff62\uff63\uff64\uff65\uff66\uff67\uff68\uff69\uff6a"
            "\uff6b\uff6c\uff6d\uff6e\uff6f\uff70\uff71\uff72\uff73\uff74"
            "\uff75\uff76\uff77\uff78\uff79\uff7a\uff7b\uff7c\uff7d\uff7e"
            "\uff7f\uff80\uff81\uff82\uff83\uff84\uff85\uff86\uff87\uff88"
            "\uff89\uff8a\uff8b\uff8c\uff8d\uff8e\uff8f\uff90\uff91\uff92"
            "\uff93\uff94\uff95\uff96\uff97\uff98\uff99\uff9a\uff9b\uff9c"
            "\uff9d\uff9e\uff9f")           # 0xA1 .. 0xDF

# Decode $A0-$FE as high-bit English rather than katakana. Off by default so
# stock files read correctly; turn on for patched files.
HIGH_BIT_ENGLISH = bool(os.environ.get('SR_EN'))

try:
    from hwmap import PRECOMPOSED
except ImportError:                          # fall back to the confirmed subset
    PRECOMPOSED = {0x9E: '\u30dd', 0xEC: '\u30b8', 0xFA: '\u30d0'}


def hw_word(w):
    """One half-width WORD -> two display characters.

    $A0-$FE is AMBIGUOUS BY DESIGN: those byte values are half-width katakana
    in stock data and high-bit English in a patched file (see FORMAT.md), and
    nothing in the bytes distinguishes them. So this is a MODE, not a guess.
    Set HIGH_BIT_ENGLISH (or pass --en / SR_EN=1) when decoding a patched file.
    """
    hi, lo = w >> 8, w & 0xFF
    if HIGH_BIT_ENGLISH and w >= 0xA0A0 and all(0xA0 <= b <= 0xFE for b in (hi, lo)):
        return chr(hi & 0x7F) + chr(lo & 0x7F)
    return hw_char(hi) + hw_char(lo)


def hw_char(b):
    """One half-width byte -> a display character."""
    if b in PRECOMPOSED:
        return PRECOMPOSED[b]
    if 0x20 <= b <= 0x7E:
        return chr(b)
    if 0xA1 <= b <= 0xDF:
        return JIS_KANA[b - 0xA1]
    return '<%02X>' % b


# ------------------------------------------------------------------- parsing
class Line:
    __slots__ = ('off', 'words')

    def __init__(self, off, words):
        self.off, self.words = off, words

    @property
    def cells(self):
        return len(self.words)

    @property
    def budget(self):
        """Latin characters available if this line is replaced word-for-word."""
        return len(self.words) * 2

    def text(self, table):
        out = []
        for w in self.words:
            if FW_LO <= w < FW_HI:
                i = w & 0x7FFF
                out.append(table.get(i, '<%d>' % i) if table else '<%d>' % i)
            else:
                out.append(hw_word(w))
        return ''.join(out).rstrip()


class Block:
    __slots__ = ('off', 'ctl_off', 'ctl', 'kind', 'win', 'count',
                 'speaker', 'flag', 'extra', 'lines')

    def __init__(self):
        self.win = self.count = self.speaker = self.flag = self.extra = None
        self.lines = []
        self.ctl = []

    @property
    def cells(self):
        return sum(l.cells for l in self.lines)

    @property
    def budget(self):
        return self.cells * 2


def is_cell(v):
    """Could this word be a text cell (full-width, or two half-width glyphs)?

    Used only to find where the text region starts. It must accept half-width
    text, because a TRANSLATED file has English at the very first line -- an
    earlier version of this walked back over full-width words only and so
    started 11 words late on any patched file, silently dropping block 0.
    Binary before the region is rejected because 68k data words are dense in
    bytes below $20, which is a control/blank region in FONT86.G.
    """
    if FW_LO <= v < FW_HI:
        return True
    hi, lo = v >> 8, v & 0xFF
    return all(0x20 <= b <= 0x7E or 0x9A <= b <= 0xFF for b in (hi, lo))


def find_region(data):
    """(start, end) byte offsets of the text region."""
    w = [struct.unpack_from('>H', data, i)[0] for i in range(0, len(data) - 1, 2)]
    first = next(i for i, v in enumerate(w) if v == NEWLINE)
    b = first
    while b > 0 and is_cell(w[b - 1]):
        b -= 1
    while b > 0 and (w[b - 1] in WIN or 0 < w[b - 1] < 0x20
                     or w[b - 1] in EXTRA):
        b -= 1
    last = max(i for i, v in enumerate(w) if v == NEWLINE)
    return b * 2, (last + 1) * 2


def match_ctl(w, p, n):
    """Match a control run at word index p. Returns (newp, fields) or (p, None)."""
    q = p
    f = {}
    if q < n and w[q] in WIN:
        f['win'] = w[q]
        q += 1
    if q < n and 0 < w[q] < 0x20:
        f['count'] = w[q]
        q += 1
    if q + 2 < n and w[q] == PORTRAIT:
        f['speaker'] = w[q + 1]
        f['flag'] = w[q + 2]
        q += 3
    if q < n and w[q] in EXTRA:
        f['extra'] = w[q]
        q += 1
    return (q, f) if f else (p, None)


def parse(data, start=None, end=None):
    """Yield Block objects covering the whole text region."""
    if start is None:
        start, end = find_region(data)
    w = [struct.unpack_from('>H', data, i)[0] for i in range(0, len(data) - 1, 2)]
    n = end // 2
    p = start // 2
    blk = None
    while p < n:
        q, f = match_ctl(w, p, n)
        if f is not None:
            if blk is not None:
                yield blk
            blk = Block()
            blk.ctl_off = p * 2
            blk.ctl = w[p:q]
            blk.win = f.get('win')
            blk.count = f.get('count')
            blk.speaker = f.get('speaker')
            blk.flag = f.get('flag')
            blk.extra = f.get('extra')
            blk.kind = 'count' if 'count' in f else 'page'
            blk.off = q * 2
            p = q
            continue
        if blk is None:                       # region starts mid-stream
            blk = Block()
            blk.ctl_off = blk.off = p * 2
            blk.kind = 'page'
        # one line
        s = p
        while p < n and w[p] != NEWLINE:
            p += 1
        blk.lines.append(Line(s * 2, w[s:p]))
        p += 1                                 # consume the $0D0A
        if blk.kind == 'count' and len(blk.lines) >= blk.count:
            yield blk
            blk = None
    if blk is not None:
        yield blk


# ------------------------------------------------------------------ commands
def read_table(path):
    tab = {}
    for ln in open(path, encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t')
        if len(c) >= 3 and c[2]:
            tab[int(c[0])] = c[2]
    return tab


def spk(b):
    if b.speaker is None:
        return ''
    return '%04X' % b.speaker


def cmd_blocks(text, table=None):
    data = open(text, 'rb').read()
    tab = read_table(table) if table else {}
    nb = nl = nc = 0
    for b in parse(data):
        nb += 1
        nl += len(b.lines)
        nc += b.cells
        head = ' '.join('%04X' % x for x in b.ctl) or '-'
        print('=== 0x%06X  %-5s  ctl[%s]  %d lines  %d cells  %d chars'
              % (b.off, b.kind, head, len(b.lines), b.cells, b.budget))
        for l in b.lines:
            print('    0x%06X %2dc %2dch  %s'
                  % (l.off, l.cells, l.budget, l.text(tab)))
    print('\n%d blocks, %d lines, %d cells' % (nb, nl, nc))


def cmd_counts(text, out):
    data = open(text, 'rb').read()
    c = Counter()
    for b in parse(data):
        for l in b.lines:
            for w in l.words:
                if FW_LO <= w < FW_HI:
                    c[w & 0x7FFF] += 1
    with open(out, 'w', encoding='utf-8') as f:
        f.write('index\tcount\n')
        for i in sorted(c):
            f.write('%d\t%d\n' % (i, c[i]))
    print('%s: %d distinct indices, %d total glyphs, max index %d'
          % (out, len(c), sum(c.values()), max(c)))


def cmd_sheet(text, table, out):
    data = open(text, 'rb').read()
    tab = read_table(table)
    rows = 0
    with open(out, 'w', encoding='utf-8') as f:
        f.write('block\tline\toffset\tkind\tspeaker\tflag\twin\tcells\t'
                'budget\tjapanese\tenglish\n')
        for bi, b in enumerate(parse(data)):
            for li, l in enumerate(b.lines):
                f.write('%d\t%d\t0x%06X\t%s\t%s\t%s\t%s\t%d\t%d\t%s\t\n'
                        % (bi, li, l.off, b.kind, spk(b),
                           '' if b.flag is None else '%04X' % b.flag,
                           '' if b.win is None else '%04X' % b.win,
                           l.cells, l.budget, l.text(tab)))
                rows += 1
    print('%s: %d lines' % (out, rows))


def cmd_verify(text):
    data = open(text, 'rb').read()
    start, end = find_region(data)
    claimed = 0
    for b in parse(data):
        claimed += len(b.ctl) + sum(l.cells + 1 for l in b.lines)
    total = (end - start) // 2
    print('region 0x%06X-0x%06X = %d words' % (start, end, total))
    print('claimed by parser        = %d words' % claimed)
    print('UNACCOUNTED              = %d' % (total - claimed))


if __name__ == '__main__':
    argv = [a for a in sys.argv if a != '--en']
    if len(argv) != len(sys.argv):
        HIGH_BIT_ENGLISH = True
    sys.argv = argv
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    {'blocks': cmd_blocks, 'sheet': cmd_sheet, 'counts': cmd_counts,
     'verify': cmd_verify}[sys.argv[1]](*sys.argv[2:])
