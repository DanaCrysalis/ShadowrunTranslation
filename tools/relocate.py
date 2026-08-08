#!/usr/bin/env python3
"""
relocate.py - relocate a dialogue block into the zero tail of an ADV_*.D file,
expand it, and repoint its `001D <offset>` entry in the event bytecode.

Non-destructive: the original block is left in place and simply orphaned.
"""
import struct, sys

HI = lambda s: bytes((ord(c) | 0x80) for c in s)   # ASCII -> high-bit encoding

def enc_line(text, cells):
    """Encode one line: `cells` words, 2 high-bit Latin chars per word."""
    if len(text) > cells * 2:
        raise SystemExit(f"line too long: {len(text)} chars > {cells*2} budget")
    return HI(text.ljust(cells * 2))

def find_entries(d, target, head_end):
    """Every `001D <target>` site in the event bytecode."""
    out = []
    for o in range(0, head_end - 3, 2):
        if struct.unpack_from('>H', d, o)[0] == 0x001D and \
           struct.unpack_from('>H', d, o + 2)[0] == target:
            out.append(o + 2)
    return out

def tail_start(d):
    i = len(d)
    while i > 0 and d[i - 1] == 0:
        i -= 1
    return i

def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = bytearray(open(src, 'rb').read())

    ENTRY      = 0x3840     # block start (the $2100 portrait word)
    OLD_END    = 0x3878     # word after the block = the $2323 that terminates it
    HEAD_END   = 0x33A4
    CARRY      = 2048       # bytes of original stream copied after our block

    lines = [
        ("Same old Silver Moon. Nothing",     16),
        ("here ever changes, and the whole",  16),
        ("crew is already waiting for us.",   16),
    ]

    tail = tail_start(d)
    print(f"tail starts at 0x{tail:05X}, {len(d)-tail} bytes free")

    # --- build the relocated block -------------------------------------
    blk  = bytearray()
    blk += struct.pack('>HHH', 0x2100, 0x0000, 0x0000)   # portrait, as original
    blk += struct.pack('>H', 0x63C8)                     # param, as original
    for text, cells in lines:
        blk += enc_line(text, cells)
        blk += struct.pack('>H', 0x0D0A)
    blk += struct.pack('>H', 0x2323)                     # terminator, as original

    orig_len = OLD_END - ENTRY
    print(f"original block: {orig_len} bytes ({orig_len//2} words)")
    print(f"new block     : {len(blk)} bytes ({len(blk)//2} words)  "
          f"[{len(blk)//2 - 4 - len(lines)} text cells]")

    if tail + len(blk) + CARRY > len(d):
        raise SystemExit("does not fit in tail")

    # --- write block + carry copy of the original following stream -----
    d[tail:tail + len(blk)] = blk
    carry_src = OLD_END + 2                    # first word of the NEXT block
    d[tail + len(blk): tail + len(blk) + CARRY] = d[carry_src: carry_src + CARRY]

    # --- repoint the entry ---------------------------------------------
    sites = find_entries(d, ENTRY, HEAD_END)
    if not sites:
        raise SystemExit(f"no 001D entry found for 0x{ENTRY:04X}")
    for s in sites:
        struct.pack_into('>H', d, s, tail)
        print(f"repointed 001D operand at head 0x{s:05X}: "
              f"0x{ENTRY:04X} -> 0x{tail:04X}")

    assert len(d) == 65536, "file size changed"
    open(dst, 'wb').write(d)
    print(f"wrote {dst}")

if __name__ == '__main__':
    main()
