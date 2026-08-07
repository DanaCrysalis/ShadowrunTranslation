import sys
from capstone import *
BASE = 0x00010000
d = open('SRUN_S.PRG','rb').read()
md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN | CS_MODE_M68K_000)
def dis(off, n=40, label=''):
    print('--- %s  file 0x%04X  (sub $%06X)' % (label, off, BASE+off))
    for i in md.disasm(d[off:off+n*6], BASE+off):
        print('  %06X  %-22s %s %s' % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        n -= 1
        if n <= 0: break
for a in sys.argv[1:]:
    off, cnt = (a.split(':') + ['30'])[:2]
    dis(int(off,16), int(cnt))
