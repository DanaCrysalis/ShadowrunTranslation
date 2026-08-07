#!/usr/bin/env python3
"""
binpatch.py -- splice a modified file back into a Sega CD disc image.

  python3 binpatch.py disc.bin ADV_01.D ADV_01_test2.D disc_patched.bin

Arguments: the disc image, the ORIGINAL file (as extracted), the PATCHED file,
and the output image. The two files must be the same length.

Handles both common layouts:
  * 2048 bytes/sector (.iso)      -- flat splice
  * 2352 bytes/sector (.bin/.cue) -- user data is interleaved with sync,
    header and EDC/ECC, so the patch is applied per sector and the EDC/ECC
    of every touched sector is recomputed.

SAFETY: before writing anything, the tool recomputes EDC/ECC for sectors it is
NOT modifying and checks the result matches the bytes already in the image. If
that self-check fails, its ECC implementation does not match your image and it
refuses to write. Use --no-ecc to splice anyway (fine for most emulators,
risky on hardware).
"""
import sys

# ---------------------------------------------------------------- ECC tables
ECC_F = [0] * 256
ECC_B = [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    ECC_F[_i] = _j
    ECC_B[_i ^ _j] = _i

EDC_LUT = []
for _i in range(256):
    _e = _i
    for _ in range(8):
        _e = (_e >> 1) ^ (0xD8018001 if _e & 1 else 0)
    EDC_LUT.append(_e)


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC_LUT[(e ^ b) & 0xFF]
    return e & 0xFFFFFFFF


def _ecc_block(src, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        out[major] = a
        out[major + major_count] = a ^ b
    return bytes(out)


def ecc_pq(sector, zero_address):
    """Return (P, Q) parity for a 2352-byte sector."""
    s = bytearray(sector)
    if zero_address:
        s[0x0C:0x10] = b'\0\0\0\0'
    body = s[0x0C:0x81C]
    p = _ecc_block(body, 86, 24, 2, 86)
    q = _ecc_block(body + p, 52, 43, 86, 88)
    return p, q


def fix_sector(sec):
    """Recompute EDC + ECC in place for one 2352-byte Mode 1 / Mode 2 Form 1
    sector. Returns the repaired sector, or None if the mode is unsupported."""
    s = bytearray(sec)
    mode = s[0x0F]
    if mode == 1:
        s[0x810:0x814] = edc(s[0x000:0x810]).to_bytes(4, 'little')
        s[0x814:0x81C] = b'\0' * 8
        zero_addr = False
    elif mode == 2 and (s[0x12] & 0x20) == 0:      # Form 1
        s[0x818:0x81C] = edc(s[0x010:0x818]).to_bytes(4, 'little')
        zero_addr = True
    else:
        return None
    p, q = ecc_pq(s, zero_addr)
    s[0x81C:0x8C8] = p
    s[0x8C8:0x930] = q
    return bytes(s)


# ---------------------------------------------------------------- layout
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def detect(img):
    if len(img) % 2352 == 0 and img[:12] == SYNC:
        return 2352
    if len(img) % 2048 == 0:
        return 2048
    raise SystemExit('cannot determine sector size (len=%d)' % len(img))


def user_span(sec):
    """(start, length) of user data within a 2352-byte sector."""
    mode = sec[0x0F]
    if mode == 1:
        return 0x010, 2048
    if mode == 2:
        return 0x018, 2048
    return None


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    no_ecc = '--no-ecc' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    img_p, orig_p, patch_p, out_p = args[:4]

    img = bytearray(open(img_p, 'rb').read())
    orig = open(orig_p, 'rb').read()
    new = open(patch_p, 'rb').read()
    if len(orig) != len(new):
        raise SystemExit('file lengths differ (%d vs %d) -- refusing'
                         % (len(orig), len(new)))
    ss = detect(img)
    print('image: %d bytes, %d-byte sectors, %d sectors'
          % (len(img), ss, len(img) // ss))

    if ss == 2048:
        n = img.count(orig)
        if n != 1:
            raise SystemExit('found %d copies of %s in the image -- '
                             'refusing (need exactly 1)' % (n, orig_p))
        at = img.find(orig)
        img[at:at + len(orig)] = new
        print('spliced at 0x%X, %d bytes changed'
              % (at, sum(a != b for a, b in zip(orig, new))))
        open(out_p, 'wb').write(img)
        return

    # ---- 2352: build a view of user data only
    nsec = len(img) // 2352
    spans = []
    view = bytearray()
    for i in range(nsec):
        sec = img[i * 2352:(i + 1) * 2352]
        sp = user_span(sec)
        if sp is None:
            spans.append(None)
            continue
        st, ln = sp
        spans.append((i, st, ln, len(view)))
        view += sec[st:st + ln]

    n = view.count(orig)
    if n != 1:
        raise SystemExit('found %d copies of %s in the image -- '
                         'refusing (need exactly 1)' % (n, orig_p))
    at = view.find(orig)
    changed = [at + k for k in range(len(orig)) if orig[k] != new[k]]
    print('file found at user-data offset 0x%X, %d bytes to change'
          % (at, len(changed)))

    # which sectors are touched
    touched = set()
    for e in spans:
        if e is None:
            continue
        i, st, ln, vo = e
        for c in changed:
            if vo <= c < vo + ln:
                touched.add(i)
    print('sectors touched: %s' % sorted(touched))

    # ---- self-check ECC on untouched sectors
    if not no_ecc:
        checked = ok = 0
        for e in spans:
            if e is None or checked >= 16:
                continue
            i, st, ln, vo = e
            if i in touched:
                continue
            sec = bytes(img[i * 2352:(i + 1) * 2352])
            rep = fix_sector(sec)
            if rep is None:
                continue
            checked += 1
            ok += (rep == sec)
        print('ECC self-check: %d/%d untouched sectors reproduced exactly'
              % (ok, checked))
        if checked == 0 or ok != checked:
            raise SystemExit(
                'ECC self-check FAILED -- this image uses a layout or error-'
                'correction scheme this tool does not reproduce. Re-run with '
                '--no-ecc to splice without repairing EDC/ECC (usually fine '
                'in emulators, may fail on hardware).')

    # ---- apply
    view[at:at + len(new)] = new
    for e in spans:
        if e is None:
            continue
        i, st, ln, vo = e
        if i not in touched:
            continue
        base = i * 2352
        img[base + st:base + st + ln] = view[vo:vo + ln]
        if not no_ecc:
            rep = fix_sector(bytes(img[base:base + 2352]))
            if rep is not None:
                img[base:base + 2352] = rep
    open(out_p, 'wb').write(img)
    print('wrote %s (%d bytes, length unchanged: %s)'
          % (out_p, len(img), len(img) == len(open(img_p, 'rb').read())))


if __name__ == '__main__':
    main()
