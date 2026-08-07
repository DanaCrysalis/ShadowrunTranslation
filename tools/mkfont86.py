#!/usr/bin/env python3
"""
mkfont86.py -- rebuild FONT86.G with Latin punctuation in the ASCII slots.

FONT86.G is 256 glyphs x 8x16 px, 1bpp, one byte per row, indexed at true
ASCII / JIS X 0201. Letters and digits are already correct; the punctuation
slots hold status-screen kanji. The renderer masks the index with $FF, so
there is no room to grow -- punctuation must displace those kanji.

Metrics matched to the existing face: caps occupy rows 0..14 (baseline row
14), descenders reach row 15, ink stays inside columns 1..6.

  python3 mkfont86.py FONT86.G FONT86_en.G [--minimal]

--minimal fills only the slots English cannot do without, leaving the other
kanji intact:  . , ' - ? ! : ( ) "
"""
import sys

BASE = "........"

G = {}


def g(ch, *rows):
    assert len(rows) == 16, (ch, len(rows))
    for r in rows:
        assert len(r) == 8, (ch, r)
    G[ch] = rows


g('!', "...##...", "...##...", "...##...", "...##...", "...##...",
       "...##...", "...##...", "...##...", "...##...", "...##...",
       BASE, BASE, BASE, "...##...", "...##...", BASE)

g('"', "..#..#..", "..#..#..", "..#..#..", "..#..#..", BASE, BASE, BASE,
       BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE)

g('#', BASE, "..#..#..", "..#..#..", "..#..#..", ".######.", "..#..#..",
       "..#..#..", "..#..#..", ".######.", "..#..#..", "..#..#..",
       "..#..#..", BASE, BASE, BASE, BASE)

g('$', "...#....", "...#....", "..####..", ".#.#..#.", ".#.#....",
       ".#.#....", "..####..", "....#.#.", "....#.#.", "....#.#.",
       ".#..#.#.", "..####..", "...#....", "...#....", BASE, BASE)

g('%', ".##...#.", ".##..#..", ".##..#..", "....#...", "....#...",
       "...#....", "...#....", "..#.....", "..#.....", ".#...##.",
       ".#...##.", "#....##.", BASE, BASE, BASE, BASE)

g('&', "..##....", ".#..#...", ".#..#...", ".#..#...", "..##....",
       "..##....", ".#..#.#.", "#....#..", "#....#..", "#...#.#.",
       "#..#..#.", ".##...#.", BASE, BASE, BASE, BASE)

g("'", "...##...", "...##...", "...##...", "...##...", BASE, BASE, BASE,
       BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE)

g('(', "....#...", "...#....", "..#.....", "..#.....", ".#......",
       ".#......", ".#......", ".#......", ".#......", ".#......",
       ".#......", "..#.....", "..#.....", "...#....", "....#...", BASE)

g(')', "...#....", "....#...", ".....#..", ".....#..", "......#.",
       "......#.", "......#.", "......#.", "......#.", "......#.",
       "......#.", ".....#..", ".....#..", "....#...", "...#....", BASE)

g('*', BASE, "...#....", ".#.#.#..", "..###...", "...#....", "..###...",
       ".#.#.#..", "...#....", BASE, BASE, BASE, BASE, BASE, BASE, BASE,
       BASE)

g('+', BASE, BASE, BASE, "...#....", "...#....", "...#....", ".######.",
       "...#....", "...#....", "...#....", BASE, BASE, BASE, BASE, BASE,
       BASE)

g(',', BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE,
       BASE, "...##...", "...##...", "..##....", "..#.....")

g('-', BASE, BASE, BASE, BASE, BASE, BASE, ".#####..", BASE, BASE, BASE,
       BASE, BASE, BASE, BASE, BASE, BASE)

g('.', BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE,
       BASE, BASE, "...##...", "...##...", BASE)

g('/', "......#.", "......#.", ".....#..", ".....#..", "....#...",
       "....#...", "...#....", "...#....", "..#.....", "..#.....",
       ".#......", ".#......", "#.......", "#.......", BASE, BASE)

g(':', BASE, BASE, BASE, "...##...", "...##...", BASE, BASE, BASE, BASE,
       BASE, BASE, BASE, BASE, "...##...", "...##...", BASE)

g(';', BASE, BASE, BASE, "...##...", "...##...", BASE, BASE, BASE, BASE,
       BASE, BASE, BASE, "...##...", "...##...", "..##....", "..#.....")

g('<', BASE, BASE, "......#.", ".....#..", "....#...", "...#....",
       "..#.....", "...#....", "....#...", ".....#..", "......#.", BASE,
       BASE, BASE, BASE, BASE)

g('=', BASE, BASE, BASE, BASE, ".######.", BASE, BASE, ".######.", BASE,
       BASE, BASE, BASE, BASE, BASE, BASE, BASE)

g('>', BASE, BASE, ".#......", "..#.....", "...#....", "....#...",
       ".....#..", "....#...", "...#....", "..#.....", ".#......", BASE,
       BASE, BASE, BASE, BASE)

g('?', "..####..", ".#....#.", ".#....#.", "......#.", "......#.",
       ".....#..", "....#...", "...#....", "...#....", BASE, BASE, BASE,
       BASE, "...##...", "...##...", BASE)

g('@', "..####..", ".#....#.", "#......#", "#..###.#", "#.#..#.#",
       "#.#..#.#", "#.#..#.#", "#..####.", "#.......", "#.......",
       ".#....#.", "..####..", BASE, BASE, BASE, BASE)

g('[', "..####..", "..#.....", "..#.....", "..#.....", "..#.....",
       "..#.....", "..#.....", "..#.....", "..#.....", "..#.....",
       "..#.....", "..#.....", "..#.....", "..#.....", "..####..", BASE)

g('\\', ".#......", ".#......", "..#.....", "..#.....", "...#....",
        "...#....", "....#...", "....#...", ".....#..", ".....#..",
        "......#.", "......#.", ".......#", ".......#", BASE, BASE)

g(']', "..####..", ".....#..", ".....#..", ".....#..", ".....#..",
       ".....#..", ".....#..", ".....#..", ".....#..", ".....#..",
       ".....#..", ".....#..", ".....#..", ".....#..", "..####..", BASE)

g('^', "...##...", "..#..#..", ".#....#.", BASE, BASE, BASE, BASE, BASE,
       BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE)

g('_', BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE,
       BASE, BASE, BASE, BASE, "########")

g('`', "..##....", "...#....", "....#...", BASE, BASE, BASE, BASE, BASE,
       BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE)

g('{', "....##..", "...#....", "...#....", "...#....", "...#....",
       "...#....", "..#.....", "...#....", "...#....", "...#....",
       "...#....", "...#....", "...#....", "...#....", "....##..", BASE)

g('|', "...#....", "...#....", "...#....", "...#....", "...#....",
       "...#....", "...#....", "...#....", "...#....", "...#....",
       "...#....", "...#....", "...#....", "...#....", "...#....", BASE)

g('}', "..##....", "....#...", "....#...", "....#...", "....#...",
       "....#...", ".....#..", "....#...", "....#...", "....#...",
       "....#...", "....#...", "....#...", "....#...", "..##....", BASE)

g('~', BASE, BASE, BASE, BASE, BASE, "..#...#.", ".#.#.#..", ".#..#...",
       BASE, BASE, BASE, BASE, BASE, BASE, BASE, BASE)

MINIMAL = set(".,'-?!:()\"")


def pack(rows):
    out = bytearray(16)
    for y, r in enumerate(rows):
        b = 0
        for x, c in enumerate(r):
            if c == '#':
                b |= 1 << (7 - x)
        out[y] = b
    return bytes(out)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    minimal = '--minimal' in sys.argv
    data = bytearray(open(src, 'rb').read())
    assert len(data) == 4096, len(data)
    wanted = sorted(G, key=ord)
    if minimal:
        wanted = [c for c in wanted if c in MINIMAL]
    touched = []
    for ch in wanted:
        i = ord(ch)
        old = bytes(data[i * 16:(i + 1) * 16])
        data[i * 16:(i + 1) * 16] = pack(G[ch])
        touched.append((i, ch, any(old)))
    open(dst, 'wb').write(bytes(data))
    print('%s: %d slots written (%s set)'
          % (dst, len(touched), 'minimal' if minimal else 'full'))
    for i, ch, had in touched:
        print('  0x%02X  %-2r  %s' % (i, ch, 'displaced a kanji' if had
                                      else 'slot was empty'))


if __name__ == '__main__':
    main()
