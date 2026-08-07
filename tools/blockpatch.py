#!/usr/bin/env python3
"""
blockpatch.py -- write English into a Shadowrun ADV file a BLOCK at a time,
with the line breaks free to move.

hwpatch.py is line-locked on purpose: it computes each line's length from the
$0D0A already in the file and refuses to write past it. That is the right
default while findings §11.1 is unanswered. This tool relaxes it by exactly one
degree:

    the total WORD COUNT of the block is held identical
    ($0D0A counts as one word, like any cell)
    ...but the words may be distributed across lines however you like.

So the block still occupies exactly its original bytes, the file length never
changes, and no offset outside the block moves. What changes is only where the
newlines sit inside it -- which is precisely the thing §11.1 asks about.

Patch file format (TSV), one block per record:

    #                       comment
    @<hex offset>           start of a block (first cell, not the control run)
    <text>                  one output line
    <text>                  another output line
    ...                     blank line or next @ ends the record

Reserved values are enforced exactly as in hwpatch.py: $0D0A, the
$8000-$99FF full-width window, and high bytes $21 / $23 / $24.

  python3 blockpatch.py ADV_01.D ADV_01_reflow.D reflow.tsv
"""
import struct
import sys

NEWLINE = 0x0D0A
RESERVED_HI = (0x21, 0x23, 0x24)


def block_words(data, off):
    """Total words from off up to and including the block's last $0D0A.

    A block ends where the next control run begins. Control runs only ever
    start at a line start, so: walk lines until the word after a $0D0A is not
    plain text.
    """
    n = 0
    p = off
    end = len(data) - 1
    while p < end:
        v = struct.unpack_from('>H', data, p)[0]
        n += 1
        p += 2
        if v != NEWLINE:
            continue
        if p >= end:
            break
        nxt = struct.unpack_from('>H', data, p)[0]
        if nxt in (0x2323, 0x2424) or 0 < nxt < 0x20 or nxt == 0x2100 \
                or nxt in (0x63C8, 0x63F8) or nxt == 0:
            break
    return n


def encode_line(text):
    """ASCII -> words. Odd length is padded with a trailing space."""
    if len(text) % 2:
        text += ' '
    words = []
    for i in range(0, len(text), 2):
        hi, lo = ord(text[i]), ord(text[i + 1])
        if hi > 0xFF or lo > 0xFF:
            raise ValueError('non-Latin-1 character in %r' % text)
        w = (hi << 8) | lo
        if w == NEWLINE or 0x8000 <= w < 0x9A00 or hi in RESERVED_HI:
            raise ValueError(
                'reserved word $%04X from %r in %r -- shift the parity by '
                'padding one character' % (w, text[i:i + 2], text))
        words.append(w)
    return words


def build(lines):
    out = []
    for t in lines:
        out += encode_line(t)
        out.append(NEWLINE)
    return out


def read_patch(path):
    recs = []
    cur = None
    for raw in open(path, encoding='utf-8'):
        s = raw.rstrip('\n').rstrip('\r')
        if s.startswith('#'):
            continue
        if s.startswith('@'):
            if cur:
                recs.append(cur)
            cur = (int(s[1:].strip(), 16), [])
            continue
        if not s.strip():
            continue
        if cur is None:
            raise SystemExit('text before any @offset: %r' % s)
        cur[1].append(s)
    if cur:
        recs.append(cur)
    return recs


def main():
    src, dst, tsv = sys.argv[1:4]
    data = bytearray(open(src, 'rb').read())
    orig = bytes(data)
    for off, lines in read_patch(tsv):
        have = block_words(orig, off)
        words = build(lines)
        if len(words) != have:
            raise SystemExit(
                '0x%06X: block is %d words, patch is %d '
                '(%d lines x cells + %d newlines). Adjust the line lengths -- '
                'the total must match exactly.'
                % (off, have, len(words), len(lines), len(lines)))
        for k, w in enumerate(words):
            struct.pack_into('>H', data, off + 2 * k, w)
        cells = [len(l) + (len(l) % 2) >> 0 for l in lines]
        print('0x%06X  %d words  %d lines  cells=%s'
              % (off, have, len(lines),
                 '/'.join(str((len(l) + 1) // 2) for l in lines)))
        for l in lines:
            print('      |%s|' % l)
    assert len(data) == len(orig), 'LENGTH CHANGED -- do not use'
    open(dst, 'wb').write(bytes(data))
    diff = sum(1 for a, b in zip(orig, data) if a != b)
    print('\n%s: %d bytes differ, length unchanged (%d)'
          % (dst, diff, len(data)))


if __name__ == '__main__':
    main()
