import sys
from capstone import *
f = sys.argv[1]; base = int(sys.argv[2],16)
d = open(f,'rb').read()
md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN | CS_MODE_M68K_000)
for a in sys.argv[3:]:
    off, cnt = (a.split(':') + ['30'])[:2]
    off, n = int(off,16), int(cnt)
    print('--- %s  file 0x%05X' % (f, off))
    for i in md.disasm(d[off:off+n*8], base+off):
        print('  %06X  %-20s %s %s' % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        n -= 1
        if n <= 0: break
