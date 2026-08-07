#!/usr/bin/env python3
"""
srtext.py -- Shadowrun (Sega CD, JP) text tool

Format notes (reverse-engineered):
  Font  : 16x14 px, 1bpp, column-major. 14 bytes left half + 14 bytes right half
          = 28 bytes/glyph. Flat array, no header, no compression.
  Text  : big-endian 16-bit stream inside ADV_*.D / BTL_*.D
            0x8000-0x99FF : character, glyph index = value & 0x7FFF
            0x0D0A        : newline
            < 0x8000      : script control code
  Pairing: ADV_NN.D uses KANJI_NN.K   (BTL/MSG banks pair similarly)
  Engine : Sub CPU (SRUN_S.PRG) renders text. Glyph fetch at 0x12D2 / 0x13F0 /
           0x167E, each doing  ANDI.L #$7FFF / MULU.W #28 / LEA $00054000.
           Font buffer base $054000 is hardcoded in all three sites.

Commands:
  atlas   FONT.K out.png              glyph sheet with indices, for building a table
  dump    TEXT.D FONT.K outdir/       every string -> PNG + manifest.tsv
  table   TEXT.D FONT.K table.tsv     stub char table (fill in the 'char' column)
  decode  TEXT.D table.tsv out.txt    decode script to UTF-8 using a filled table
  encode  script.txt table.tsv out.bin  re-encode edited script back to codes
"""
import sys, os, struct
from PIL import Image, ImageDraw

PITCH, GW, GH = 28, 16, 14
CHAR_LO, CHAR_HI, NEWLINE = 0x8000, 0x9A00, 0x0D0A


def load_font(path):
    d = open(path, 'rb').read()
    n = len(d.rstrip(b'\x00')) // PITCH
    return d, n


def glyph_img(fd, i, invert=False):
    im = Image.new('1', (GW, GH), 1)
    px = im.load()
    g = fd[i*PITCH:(i+1)*PITCH]
    if len(g) < PITCH:
        return im
    for y in range(GH):
        for x in range(GW):
            if (g[(x//8)*GH + y] >> (7 - (x % 8))) & 1:
                px[x, y] = 0
    return im


def parse(data, nglyph=None):
    """Yield (offset, [tokens]) per string. Tokens: int index, 'NL', ('CTL',v).

    nglyph bounds the valid index range: anything the bank can't render is not
    text, and rejecting it kills nearly all false positives in binary regions.
    """
    hi = CHAR_HI if nglyph is None else min(CHAR_HI, CHAR_LO + nglyph)
    w = len(data) // 2
    i = 0
    cur, start = [], None
    while i < w:
        v = struct.unpack_from('>H', data, i*2)[0]
        if CHAR_LO <= v < hi:
            if start is None:
                start = i*2
            cur.append(v & 0x7FFF)
        elif v == NEWLINE:
            if cur:
                cur.append('NL')
        else:
            if cur and any(isinstance(t, int) for t in cur):
                yield start, cur
            cur, start = [], None
        i += 1
    if cur and any(isinstance(t, int) for t in cur):
        yield start, cur


def render(tokens, fd, nglyph, scale=2):
    lines, row = [], []
    for t in tokens:
        if t == 'NL':
            lines.append(row); row = []
        else:
            row.append(t)
    if row:
        lines.append(row)
    lines = [l for l in lines] or [[]]
    wmax = max(1, max(len(l) for l in lines))
    im = Image.new('1', (wmax*GW, len(lines)*GH), 1)
    for r, l in enumerate(lines):
        for c, gi in enumerate(l):
            if 0 <= gi < nglyph:
                im.paste(glyph_img(fd, gi), (c*GW, r*GH))
    return im.resize((im.width*scale, im.height*scale), Image.NEAREST)


def cmd_atlas(font, out, cols=32):
    fd, n = load_font(font)
    cw, ch = GW+2, GH+12
    im = Image.new('RGB', (cols*cw, ((n+cols-1)//cols)*ch), 'white')
    dr = ImageDraw.Draw(im)
    for i in range(n):
        x, y = (i % cols)*cw, (i//cols)*ch
        im.paste(glyph_img(fd, i).convert('RGB'), (x+1, y+10))
        if i % 8 == 0:
            dr.text((x+1, y), str(i), fill='red')
    im = im.resize((im.width*2, im.height*2), Image.NEAREST)
    im.save(out)
    print(f'{out}: {n} glyphs')


def cmd_dump(text, font, outdir):
    os.makedirs(outdir, exist_ok=True)
    data = open(text, 'rb').read()
    fd, n = load_font(font)
    man = open(os.path.join(outdir, 'manifest.tsv'), 'w')
    man.write('id\toffset\tchars\tlines\tpng\tcodes\n')
    cnt = 0
    for off, toks in parse(data, n):
        chars = [t for t in toks if isinstance(t, int)]
        if len(chars) < 2:
            continue
        name = f'{cnt:04d}_{off:06x}.png'
        render(toks, fd, n).save(os.path.join(outdir, name))
        codes = ' '.join(str(t) if isinstance(t, int) else '/' for t in toks)
        man.write(f'{cnt}\t0x{off:06x}\t{len(chars)}\t{toks.count("NL")+1}\t{name}\t{codes}\n')
        cnt += 1
    man.close()
    print(f'{cnt} strings -> {outdir}/')


def cmd_table(text, font, out):
    data = open(text, 'rb').read()
    fd, n = load_font(font)
    used = {}
    for _, toks in parse(data, n):
        for t in toks:
            if isinstance(t, int):
                used[t] = used.get(t, 0) + 1
    with open(out, 'w') as f:
        f.write('index\tcount\tchar\n')
        for i in sorted(used):
            f.write(f'{i}\t{used[i]}\t\n')
    print(f'{out}: {len(used)} distinct glyphs of {n} in bank')


def read_table(p):
    m = {}
    for ln in open(p, encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t')
        if len(c) >= 3 and c[2].strip():
            m[int(c[0])] = c[2]
    return m


def cmd_decode(text, table, out):
    data = open(text, 'rb').read()
    tab = read_table(table)
    miss = set()
    nglyph = max(tab) + 1 if tab else None
    with open(out, 'w', encoding='utf-8') as f:
        for off, toks in parse(data, nglyph):
            f.write(f'### 0x{off:06x}\n')
            for t in toks:
                if t == 'NL':
                    f.write('\n')
                else:
                    if t not in tab:
                        miss.add(t)
                    f.write(tab.get(t, f'<{t}>'))
            f.write('\n\n')
    print(f'{out} written; {len(miss)} unmapped indices' +
          (f': {sorted(miss)[:20]}' if miss else ''))


def cmd_encode(script, table, out):
    rev = {v: k for k, v in read_table(table).items()}
    buf = bytearray()
    for ln in open(script, encoding='utf-8'):
        if ln.startswith('###'):
            continue
        for ch in ln.rstrip('\n'):
            if ch in rev:
                buf += struct.pack('>H', 0x8000 | rev[ch])
            else:
                print(f'  ! no glyph for {ch!r}')
        buf += struct.pack('>H', NEWLINE)
    open(out, 'wb').write(buf)
    print(f'{out}: {len(buf)} bytes')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    {'atlas': cmd_atlas, 'dump': cmd_dump, 'table': cmd_table,
     'decode': cmd_decode, 'encode': cmd_encode}[sys.argv[1]](*sys.argv[2:])
