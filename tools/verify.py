import struct
a=open('/mnt/user-data/uploads/ADV_01.D','rb').read()
b=open('/mnt/user-data/outputs/ADV_01_reloc.D','rb').read()

print(f"size: {len(a)} -> {len(b)}  {'OK' if len(a)==len(b) else 'CHANGED'}")
diffs=[i for i in range(len(a)) if a[i]!=b[i]]
runs=[]
for i in diffs:
    if runs and i==runs[-1][1]+1: runs[-1][1]=i
    else: runs.append([i,i])
print(f"changed byte runs: {[(hex(s),hex(e)) for s,e in runs]}")
print()

def cls(w):
    if w&0x8000:
        if w>=0xA0A0:
            lo,hi=(w>>8)&0x7F, w&0x7F
            return f"EN  '{chr(lo)}{chr(hi)}'"
        return f"FW  idx {w&0x7FFF}"
    if w==0x0D0A: return "EOL"
    return {0x21:'PORTRAIT',0x24:'PAGE',0x23:'WIN',0x63:'PARAM'}.get(w>>8,f'ctrl {w:04X}')

def dump(d,lo,hi,label):
    print(f"--- {label} 0x{lo:05X}-0x{hi:05X} ---")
    cells=0; lines=0; line=""
    for o in range(lo,hi,2):
        w=struct.unpack_from('>H',d,o)[0]
        c=cls(w)
        if c.startswith('EN'):
            line+=c[5:7]; cells+=1
        elif c.startswith('FW'):
            cells+=1
        elif c=='EOL':
            lines+=1
            if line: print(f"   line {lines}: [{line}]  ({len(line)} chars)"); line=""
            else: print(f"   line {lines}: <original japanese, {cells} cells>")
        else:
            print(f"   0x{o:05X} {c}")
    print(f"   -> {cells} text cells, {lines} lines")

dump(a,0x3840,0x387A,"ORIGINAL block")
print()
dump(b,0xD598,0xD608,"RELOCATED block")
print()
print("entry opcode check:")
for d,nm in ((a,'stock'),(b,'patched')):
    print(f"   {nm}: head 0x0059A = {struct.unpack_from('>H',d,0x59A)[0]:04X} "
          f"{struct.unpack_from('>H',d,0x59C)[0]:04X}")
print()
w=struct.unpack_from('>H',b,0xD608)[0]
print(f"carry copy first word at 0xD608 = {w:04X} ({cls(w)}), "
      f"original 0x387A = {struct.unpack_from('>H',a,0x387A)[0]:04X}")
