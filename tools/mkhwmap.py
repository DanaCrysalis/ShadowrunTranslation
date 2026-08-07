#!/usr/bin/env python3
"""Recover FONT86.G's precomposed voiced-katakana slots by bitmap diff.

A voiced glyph is its base kana plus a dakuten/handakuten mark in the top-right
corner. So: for every non-JIS slot, strip the top-right corner and look for an
exact match among the 0xA1-0xDF base kana. If the stripped corner ink matches
the dakuten pattern -> voiced; handakuten -> semi-voiced.
"""
import sys
BASE = "\uff61\uff62\uff63\uff64\uff65\uff66\uff67\uff68\uff69\uff6a\uff6b\uff6c\uff6d\uff6e\uff6f\uff70\uff71\uff72\uff73\uff74\uff75\uff76\uff77\uff78\uff79\uff7a\uff7b\uff7c\uff7d\uff7e\uff7f\uff80\uff81\uff82\uff83\uff84\uff85\uff86\uff87\uff88\uff89\uff8a\uff8b\uff8c\uff8d\uff8e\uff8f\uff90\uff91\uff92\uff93\uff94\uff95\uff96\uff97\uff98\uff99\uff9a\uff9b\uff9c\uff9d\uff9e\uff9f"
HW2FW = {}
for i,c in enumerate(BASE):
    HW2FW[0xA1+i]=c
# halfwidth->fullwidth katakana for display
import unicodedata
def wide(c):
    n = unicodedata.normalize('NFKC', c)
    return n

d = open(sys.argv[1] if len(sys.argv)>1 else 'FONT86.G','rb').read()
def rows(i): return list(d[i*16:(i+1)*16])

# candidate corner masks: try clearing the top-right N columns of the top M rows
def strip(r, cols, nrows):
    m = (0xFF >> (8-cols)) if cols<8 else 0xFF
    mask = ~(m) & 0xFF   # keep left, clear right `cols` bits
    return [(v & mask) if y < nrows else v for y,v in enumerate(r)]

base = {b: rows(b) for b in range(0xA1,0xE0)}
found = {}
report = []
for i in range(0x100):
    if 0xA1 <= i <= 0xDF: continue
    r = rows(i)
    if not any(r): continue
    for cols in (2,3,4):
        for nrows in (3,4,5,6):
            s = strip(r, cols, nrows)
            for b,br in base.items():
                if strip(br, cols, nrows) == s and br != r:
                    # corner ink of i vs base
                    if i not in found:
                        found[i]=(b,cols,nrows)
                    break
            if i in found: break
        if i in found: break
for i in sorted(found):
    b,cols,nrows = found[i]
    report.append((i,b))
print('%d candidate voiced/semi-voiced slots' % len(report))
for i,b in report:
    print('  0x%02X <- base 0x%02X (%s)' % (i,b,wide(HW2FW[b])))
