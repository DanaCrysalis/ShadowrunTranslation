# Shadowrun (Sega CD, JP) — Text Format Findings

Reverse-engineering notes for a Japanese→English translation patch.

**Status: format fully solved. English confirmed in-game in both menus and
dialogue. Dialogue blocks confirmed relocatable into free space and expandable
beyond their original cell count.** The remaining work is per-bank character
tables and the translation itself.

> **Revision 4.** Supersedes revision 3. Two changes matter. First, `ADV_*.D`
> files open with an **8-entry longword header** whose entry `[5]` is the text
> region base — region bounds are a field, not a constant (§7.1). Second, the
> **`001D` opcode** in the event bytecode is the dialogue entry instruction,
> and the dialogue handoff to the sub CPU is a **full 32-bit address**, not a
> 16-bit offset. Together these retire §11 item 4 and the word-for-word
> substitution model with it: dialogue can now be lengthened outright (§7.5,
> §9.7). Sections marked ⚠ contain corrections to revision 3.

---

## 1. Summary

| Question                  | Answer                                                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Is the text compressed?   | **No.** Uncompressed throughout.                                                                               |
| Pointer table to rebuild? | ⚠ **Yes, two.** An 8-longword file header (§7.0) and `001D` entry opcodes in the event bytecode (§7.4).        |
| Where is the script?      | `ADV_*.D` (dialogue) and `BTL_*.D` (battle)                                                                    |
| Encoding                  | Big-endian 16-bit, one word = one screen cell                                                                  |
| Text vs control           | **The main CPU tests the SIGN BIT** (§5.5). `$8000`–`$FFFF` = text; below = control code.                      |
| Full-width glyph          | `$8000`–`$99FF`, index = `value & $7FFF`                                                                       |
| Half-width pair           | `$9A00`–`$FFFF`, two glyphs, high byte then low                                                                |
| English encoding          | **`ASCII \| $80` per byte**, so every pair is ≥ `$A0A0` (§9.2)                                                  |
| Font (full-width)         | 16×14 px, 1bpp, column-major, 28 B/glyph — `KANJI*.K` at `$054000`                                              |
| Font (half-width)         | 8×16 px, 1bpp, 16 B/glyph — `FONT86.G` at `$05C000`, indexed at true ASCII                                     |
| Font↔text pairing         | `ADV_NN.D` ↔ `KANJI_NN.K`                                                                                      |
| Renderers                 | Sub CPU `SRUN_S.PRG` (load base `$00010000`); interpreter in `SRUN_X.P` / `COM_*.P` / `SRUN_M.PRG` (base `$0`) |
| English insertion         | **Working in menus and dialogue.** Verified on hardware-accurate emulation.                                    |
| Reserved characters       | **None**, in the high-bit encoding (§9.2)                                                                      |
| Can strings be lengthened?| ⚠ **Yes.** Dialogue blocks relocate into tail slack; confirmed in-game (§9.7).                                 |
| Script size (est.)        | ~150–200k characters across all files                                                                          |

---

## 2. Disc layout

1,213 files.

| Ext    | Files | Bytes    | Contents                               |
| ------ | ----- | -------- | -------------------------------------- |
| `.G`   | 951   | 48.9 MB  | Graphics **and fonts**                 |
| `.D`   | 150   | 135.4 MB | Map, battle, adventure, streamed media |
| `.P`   | 42    | 2.0 MB   | Main-CPU code overlays                 |
| `.K`   | 33    | 0.9 MB   | Full-width font banks                  |
| `.SD`  | 27    | 1.0 MB   | Sound driver / PCM                     |
| `.PRG` | 2     | 64.8 KB  | Main + Sub CPU programs                |
| `.BIN` | 2     | 8.8 KB   | Sega CD IP/SP boot                     |
| `.MSG` | 1     | 65.0 KB  | `WARNING.MSG` (unexamined)             |
| `.TXT` | 3     | 61 B     | ISO 9660 stubs — ignore                |

### Files confirmed to contain no text

- `MAP_*.D` (47 files) — tile/collision data only.
- `DUM_00.D`, `NOT_01..07.D` — 8 files of 16,180,508 bytes (~129 MB). Streamed
  video/audio.

`COM_10` and `COM_20` are 89.4% identical, so the 42 overlays share a large
common core. **That core includes the script interpreter** (§5.5), which
matters if it ever needs patching.

⚠ `SRUN_M.PRG` contains seven `MULU.W #28` sites at `0x7272`–`0x72F4`
(mirrored in `SRUN_A.P` at `0x8E38`). Still unresolved; does not affect §5.

---

## 3. Font formats

### 3.1 Full-width — `KANJI*.K`

16 × 14 px, 1bpp, column-major, 28 bytes per glyph.

```
byte  0..13  = left  8 columns (1 byte per row, top to bottom)
byte 14..27  = right 8 columns
```

```
byte = data[i*28 + (x // 8) * 14 + y]
set  = (byte >> (7 - (x % 8))) & 1
```

Flat array from offset 0. No header, no compression, no index.

### 3.2 Half-width — `FONT86.G`

8 × 16 px, 1bpp, one byte per row, 16 bytes per glyph, 256 glyphs, 4,096 bytes
exactly. Loaded to `$05C000`. **Indexed at true ASCII / JIS X 0201.**

| Range                                    | Contents                                                                   |
| ---------------------------------------- | -------------------------------------------------------------------------- |
| `0x20`–`0x7E`                            | ASCII: space, digits, `A`–`Z`, `a`–`z`, and kanji in the punctuation slots |
| `0x9A`–`0x9E`                            | **semi-voiced** katakana パピプペポ                                             |
| `0xA1`–`0xDF`                            | half-width katakana, exact JIS order                                       |
| `0xE6`–`0xF4`                            | **voiced** katakana ガギグゲゴザジズゼゾダヂヅデド                                        |
| `0xFA`–`0xFE`                            | **voiced** katakana バビブベボ                                                  |
| `0xFF`                                   | ヴ                                                                          |
| `0xE0`–`0xE5`, `0xF6`–`0xF9`, other gaps | status/equipment kanji                                                     |

**Lowercase is present in the stock font**, `a`–`z` at `0x61`–`0x7A`, with
proper descenders. No font work is needed for mixed case.

**The precomposed slots follow two exact arithmetic rules**, recovered by
bitmap-diffing the font against its own base kana (`mkhwmap.py`):

```
voiced      = base + 0x30      0xB6-0xC4 -> 0xE6-0xF4 ,  0xCA-0xCE -> 0xFA-0xFE
semi-voiced = base + 0xD0      0xCA-0xCE -> 0x9A-0x9E
0xFF        = ヴ  (ウ 0xB3 plus dakuten)
```

Note the semi-voiced block sits **below `0xA1`**. Corroboration: `0xF5` is one
of only four empty slots in the file and lands exactly at ナ + `0x30`, the
first base kana past ト with no voiced form; and all six shipped half-width
runs decode correctly (§4.2).

**Metrics:** caps occupy rows 0–14 (baseline row 14), descenders reach row 15,
ink stays within columns 1–6.

⚠ **Legibility note.** The stock lowercase `g` at `0x67` is near-indistinguishable
from `9` at 8×16 — in-game captures read "Nothin9", "chan9es", "waitin9". Not a
patch fault, but worth redrawing in `mkfont86.py` before committing to a full
script.

The renderer masks the index with `$FF`, so the file cannot grow. See §9.2 and
§9.4 for the two rebuilds.

### 3.3 Genesis 4bpp tile fonts

Three files use the Genesis 4bpp 8×8 tile format, 32 bytes per tile, on a
**different code path** from `$05C000`. Not involved in dialogue rendering.

| File       | Tiles | Used | Indexing                     | Contents                    |
| ---------- | ----- | ---- | ---------------------------- | --------------------------- |
| `ASCII.G`  | 96    | 96   | **from 0** (`0x20` → tile 0) | ASCII `0x20`–`0x7F`         |
| `FONT_8.G` | 256   | 224  | true ASCII                   | ASCII + half-width katakana |
| `FONTS8.G` | 256   | 128  | true ASCII                   | ASCII only, bolder          |

The indexing difference is a trap: mixing them up shifts text by 32 tiles.
`O_ASCI.G` (2,048 B) remains unexamined.

---

## 4. Text encoding

Big-endian 16-bit stream. **One word = one screen cell.**

| Value           | Meaning                                                       |
| --------------- | ------------------------------------------------------------- |
| `$8000`–`$99FF` | one full-width glyph, index = `value & $7FFF`, from `$054000` |
| `$9A00`–`$FFFF` | two half-width glyphs from `$05C000`, high byte then low      |
| `$0D0A`         | end of line                                                   |
| below `$8000`   | **control code** — consumed by the main CPU (§5.5)            |

`$8000` (index 0) is a full-width space.

### 4.2 Shipped half-width text

`ADV_01.D` contains six half-width runs, all whole lines:

| Offset     | Text       | Block kind  |
| ---------- | ---------- | ----------- |
| `0x003420` | シルバームーン    | count       |
| `0x003490` | オンフォール     | count       |
| `0x0034F2` | エンジェルクリニック | page (§9.6) |
| `0x003502` | ポケットセクレタリー | count       |
| `0x003548` | エンジェルクリニック | count       |
| `0x00D57C` | メッセージ      | count       |

**Five of six are in count (menu) blocks, and none of the 926 dialogue blocks
contains any half-width text at all.** That distribution is the fingerprint of
§5.5: the shipped game only ever puts half-width text where the main-CPU
interpreter is not the thing driving the draw.

---

## 5. The renderers

Text rendering is split. The **main CPU** walks the script and decides what is
text; the **sub CPU** turns text words into pixels.

Load base for `SRUN_S.PRG` is `$00010000`. `SRUN_X.P`, `COM_*.P` and
`SRUN_M.PRG` are at base `$0` (file offset = address).

### 5.1 Full-width glyph fetch (sub CPU)

Three near-identical routines at `$0112D2`, `$0113F0`, `$01167E`:

```
01167E   CMPI.W  #$8000,D0
011682   BCS.W   $01171A        ; below window -> half-width
011686   CMPI.W  #$9A00,D0
01168A   BCC.W   $01171A        ; at or above $9A00 -> half-width
01168E   ANDI.L  #$00007FFF,D0
011694   MULU.W  #28,D0
011698   LEA     $00054000,A2
01169E   ADDA.L  D0,A2
```

Loop count `MOVE.W #$D,D7` = 14 rows.

### 5.2 Half-width glyph fetch (sub CPU)

The two branches fall through to a two-glyph dispatcher at `$01138A`,
`$0114B4`, `$01171A`:

```
01171A   MOVEM.L D0,-(A7)
01171E   LSR.W   #8,D0          ; high byte
011720   BSR.W   $011728
011724   MOVEM.L (A7)+,D0       ; low byte
011728   ANDI.L  #$FF,D0
01172E   LSL.L   #4,D0          ; 16 bytes per glyph
011730   LEA     $0005C000,A2
011736   ADDA.L  D0,A2
011738   MOVE.W  #15,D7         ; 16 rows
```

Byte signature: `E9 88 45 F9 00 05 C0 00`.

### 5.3 Output footprint — equal on both paths ✅

Full-width (`$011366`, `$0116FA`) writes 16 rows of 4 bytes via `(A3)+` plus a
right-hand strip at `$40(A3)`, then `ADDA.L #$40,A3` — **128 bytes**.
Half-width (`$0113A6`, `$011728`) writes 16 rows of 4 bytes per glyph, twice —
**128 bytes**. Same byte layout.

Corroborated on the main-CPU side: `0x13AE`–`0x13B2` advances the output
pointer `$3C(A0)` by `$80` per cell.

**One source word occupies the same buffer footprint either way**, so
substitution never disturbs geometry. It also means a variable-width font is
not available without rewriting both dispatchers and the main CPU's cell-based
cursor — two Latin characters per cell is a hard ceiling.

### 5.4 The three draw loops

Only three dispatcher call sites exist in `SRUN_S.PRG`:

```
$011590  BSR.W $01167E   <- loop $01153C   DIALOGUE
$0115E4  BSR.W $0112D2   <- loop $0115A2   menu, $08xxxx mailbox
$01165C  BSR.W $0112D2   <- loop $0115FE   menu, $0Cxxxx mirror
$01179A  BSR.W $0117AA   <- atlas/debug dump
```

**Only the two menu loops count cells and lines.** `$01153C` writes neither
`$8000A` nor `$8000C`; dialogue window geometry does not come from the sub CPU
at all.

The menu loop:

```
0115CC   MOVE.W  (A1)+,D4       ; line count
0115CE   MOVE.W  D4,$8000C
0115D8   MOVE.W  (A1)+,D0
0115DA   CMPI.W  #$0D0A,D0
0115DE   BEQ.B   $115F0
0115E4   BSR.W   $112D2
0115EC   ADDQ.W  #1,D5
0115F0   MOVE.W  D5,$8000A      ; overwritten per line -> LAST line's count
0115F8   DBRA    D4,$115D8
```

The dialogue loop:

```
01154C   MOVEA.L $80054,A1      ; full 32-bit script address (§7.3)
011552   MOVE.W  $80058,$141A0  ; main-CPU parameter, purpose unknown
01156E   MOVE.W  (A1)+,D0       ; <-- loop top
011572   LSR.W   #8,D3
011574   CMPI.B  #$0D,D3
011578   BEQ.B   $1156E         ; $0Dxx -> SKIP, A3 NOT advanced
01157A   CMPI.B  #$24,D3
01157E   BEQ.W   $1158E         ; rts
011582   CMPI.B  #$23,D3
011586   BEQ.W   $1158E         ; rts
011590   BSR.W   $01167E
011594   BRA.B   $1156E
```

Two consequences. There is **no half-width filter** — the sub CPU renders
half-width in dialogue perfectly well. And **`$0D0A` is discarded** by the sub
CPU: consumed, `A3` not advanced, no row break emitted. Visual line breaks in
dialogue are produced upstream, by the main CPU's cursor (§5.5).

### 5.5 The main-CPU script interpreter

`SRUN_X.P` `0x1342` (also at `0x405E`, `COM_10.P` `0x1268`, `SRUN_M.PRG`
`0x196A` — byte-identical `3019 6B00 003E 3200 E049 0C01 0021`):

```
00133E   MOVEA.L $30(A0),A1     ; resume from the saved cursor
001342   MOVE.W  (A1)+,D0
001344   BMI.W   $1384          ; <-- SIGN BIT: set -> text
001348   MOVE.W  D0,D1
00134A   LSR.W   #8,D1
00134C   CMPI.B  #$21,D1 -> $14F2   portrait
001354   CMPI.B  #$0D,D1 -> $142C   newline
00135C   CMPI.B  #$24,D1 -> $1452   page
001364   CMPI.B  #$23,D1 -> $149E   window
00136C   CMPI.B  #$63,D1 -> $1376   parameter
001374   BNE.B   $1342          ; anything else: silently consumed
001384   MOVE.L  A1,$30(A0)     ; text: save the advanced cursor
```

**The main CPU classifies text by bit 15, not by the `$8000`–`$99FF` window.**
A plain ASCII pair such as `$5361` ("Sa") has bit 15 clear, so it falls into
the control-code dispatcher, matches nothing, and is eaten at `001374`.

⚠ **`$30(A0)` is a persistent running cursor, and inside the interpreter it is
only ever advanced — never set to a computed address.** Blocks are reached by
walking forward. Seeding is external (§7.4).

The interpreter keeps a cursor in `$28(A0)`: a **4-bit column counter in bits
7–10** and a **2-bit row counter in bits 11–12**. The newline handler only
advances the row when the column is non-zero:

```
00142C   MOVE.L  A1,$30(A0)
001430   MOVE.W  $28(A0),D0
001434   ANDI.W  #$780,D0
001438   BEQ.W   $1336          ; column still zero -> no row advance
00143C   ANDI.W  #$1800,$28(A0)
001442   ADDI.W  #$800,$28(A0)  ; bump row
```

⚠ **The column carries into the row by design.** The per-cell advance is:

```
0013C4   ADDI.W  #$80,$28(A0)
0013CA   ANDI.W  #$1F80,$28(A0)
```

`$80` is bit 7, and the mask keeps bits 7–12. A carry out of bit 10 lands in
bit 11 — so **wrapping at 16 cells is the mechanism, not a hazard**. Row
overflow past 2 bits is masked away and wraps to row 0, which *is* a hazard: a
block must still paginate with `$2424` past 3–4 rows.

**This is the whole of the failure that took six test builds to isolate.** The
sub CPU drew the English into the buffer — it was visible on screen — but the
main CPU's cursor never advanced across it, so window geometry and DMA extent
were computed as though those cells did not exist.

**`$63xx` decoded:** takes the low byte, shifts right 4, stores to `$FFC3BC`.
So `$63C8` → 12 and `$63F8` → 15.

### 5.6 File loading

`SRUN_S.PRG` holds a filename table of 1,170 fixed 8-byte records at `$011B38`
(file `0x1B38`–`0x3FC8`). `FONT86.G` is index **347 (`$15B`)**. The records
carry no size field, so load extents almost certainly come from the ISO 9660
directory.

Main-CPU code requests a file through a mailbox in work RAM:

```
MOVE.W  #index,$FFC354
MOVE.W  #mode,$FFC356      ; 0 = raw, 1 = seen on .G font loads
MOVE.L  #dest,$FFC358
BSET.B  #0,$FFC352
```

Destinations: `$03xxxx`–`$07xxxx` = sub PRG RAM, `$09xxxx`/`$0Bxxxx` = sub Word
RAM. Known loads: `ADV_NN.D` → `$090000`, `STATUS.G` → `$04E000`, `SPELL0.G` →
`$068000`, `FONTS8.G` → `$042000`.

⚠ `$FFC352` is a command register with several bits: **bit 0 = file load,
bit 1 = menu draw, bit 2 = dialogue draw** (§7.3).

---

## 6. Script grammar ✅ **closed**

`srblocks.py verify` accounts for **every word** of `ADV_01.D`'s text region,
`0x33A4`–`0xD598`, 20,730 words, zero unclaimed.

A control run occurs only at a line start (immediately after `$0D0A`, or at the
region start) and is any non-empty subset of the following, **in this fixed
order**:

| Slot       | Values             | Meaning                  |
| ---------- | ------------------ | ------------------------ |
| `WIN`      | `$2323` \| `$2424` | window / page control    |
| `CNT`      | `$0001`–`$001F`    | line-count header        |
| `PORTRAIT` | `$2100` + 2 words  | speaker portrait         |
| `EXTRA`    | `$63C8` \| `$63F8` | parameter 12 / 15 (§5.5) |

- `WIN` and `CNT` **co-occur** (`2323 0002`, `2323 0005`, …, 11 sites).
- The portrait ID is a **full word, not `[id]00`**. `$0201`, `$0202`, `$0203`
  and `$0001` all occur. **28** distinct speaker words.

### 6.1 Block types

| Kind    | Definition                                                      | Count in `ADV_01.D` |
| ------- | --------------------------------------------------------------- | ------------------- |
| `count` | run contains `CNT`; exactly `CNT` lines follow; self-delimiting | 41 (menus)          |
| `page`  | no `CNT`; lines run to the next control run                     | 926 (dialogue)      |

**967 blocks, 2,124 lines, 15,838 cells.** Block shapes: 221 × 1 line,
364 × 2, 372 × 3, 11 × 4+.

Speaker frequency: `0000` ×145, `0200` ×131, `0100` ×59, `1100` ×50, `0300` ×31,
then a long tail. ✅ **Portrait `$00` is Rokudou**, confirmed in-game.

### 6.2 `$2323` vs `$2424` — the chaining rule ⚠ **new**

The two `WIN` values are not stylistic variants. They determine **how the next
block is reached**, and therefore which blocks can move.

Of the 604 blocks that open with a `$2100` portrait word:

| Word preceding the block | Blocks | Have a `001D` entry (§7.4) |
| ------------------------ | ------ | -------------------------- |
| `$2424` PAGE             | 322    | **0 (0%)**                 |
| `$2323` WIN              | 263    | 194 (74%)                  |
| `$0D0A`                  | 12     | 9                          |
| `$2100`                  | 7      | 0                          |

- **`$2424` PAGE** — the interpreter keeps walking into the next block. Chained
  blocks **must stay contiguous with their predecessor**.
- **`$2323` WIN** — terminates the pass (the `rts` path at `0x14B4`); the event
  script re-enters with a fresh `001D`. These blocks are **freely relocatable**
  provided their `001D` operand is updated.

⚠ Residual unknown: 69 WIN-preceded blocks carry no literal `001D`. Either they
are entered by a computed offset or through another call path. Resolve before
bulk relocation.

---

## 7. Locating text within a `.D` file

### 7.0 The `ADV_*.D` file header ⚠ **new**

Each `ADV_*.D` opens with **8 longwords of absolute main-CPU addresses**. The
file loads to sub `$090000`, which the main CPU sees at `$210000`, so
`address = $210000 + file offset`.

```
+0x00 [0]    +0x08 [2]    +0x10 [4]    +0x18 [6]
+0x04 [1]    +0x0C [3]    +0x14 [5] <- TEXT REGION BASE    +0x1C [7]
```

| File       | `[0]`       | `[5]`        | Text base |
| ---------- | ----------- | ------------ | --------- |
| `ADV_01.D` | `$00210020` | `$002133A4`  | `0x33A4`  |
| `ADV_02.D` | `$00210020` | `$00212376`  | `0x2376`  |

Entries `[3]`, `[4]` and `[6]` are equal in both files sampled. The purpose of
entries other than `[5]` is not yet identified.

### 7.1 Region bounds ⚠ **corrected**

⚠ **Region bounds are a header field, not a constant.** `ADV_01.D` starts at
`0x33A4` and `ADV_02.D` at `0x2376`. Read header `[5]`; do not scan and do not
hardcode. `srblocks.find_region` should be changed accordingly.

The region ends where the zero fill begins (§7.2).

Region detection by scanning must accept **half-width cells**, not just
full-width: a translated file has English on the very first line, and a
full-width-only backward walk starts 11 words late and silently drops block 0.

### 7.2 Tail slack ⚠ **new**

Both files sampled are zero-filled from the end of the text region to `0xFFFF`.
`ADV_01`'s zero run begins at `0xD598` exactly — the region end.

| File       | Text region       | Text bytes | Free tail  | Free words |
| ---------- | ----------------- | ---------- | ---------- | ---------- |
| `ADV_01.D` | `0x33A4`–`0xD598` | 41,460     | **10,856** | 5,428      |
| `ADV_02.D` | `0x2376`–`0x8830` | 25,786     | **30,672** | 15,336     |

⚠ **The zero tail is a trap for the walk.** `$0000` has bit 15 clear, matches no
control code, and is silently consumed at `0x1374` — an interpreter that walks
into unused tail will loop there forever. Relocated blocks must be terminated
properly (§9.7).

### 7.3 String addressing ⚠ **corrected**

There are two paths, and revision 3 described only the menu one.

**Menus — 16-bit offset, `BSET #1`.** `SRUN_X.P` `0x1FA0`:

```
001FA0   MOVE.W  $34(A0),$20000E
001FA8   MOVE.L  #$0D0000,$200006
001FB2   BSET    #1,$200000
001FBE   MOVE.W  $20000A,$FFCD8E    ; cell count readback
001FC8   MOVE.W  $20000C,$FFCD90    ; line count readback
001FE8   MULU.W  D2,D1
001FEA   LSL.W   #6,D1              ; DMA length, in WORDS
```

**Dialogue — full 32-bit address, `BSET #2`.** `SRUN_X.P` `0x15DE`:

```
0015DE   MOVE.L  $30(A0),D0       ; the current running cursor
0015E2   SUBI.L  #$210000,D0      ; main WordRAM -> file offset
0015E8   ADDI.L  #$90000,D0       ; -> sub-side address
0015EE   MOVE.L  D0,$FFC368
0015F4   BSET    #2,$FFC352       ; DIALOGUE kick
0015FC   MOVE.L  #$204400,$3C(A0) ; output buffer base
```

This is what `SRUN_S.PRG` picks up as `MOVEA.L $80054,A1` (§5.4), and it
**proves the `$210000` ↔ `$090000` mapping from code** rather than inferring it.

⚠ Revision 3's "16 bits addresses the whole file" is a property of the *menu*
path and of *entry seeding* (§7.4) — **not** of the walk or the dialogue
handoff. `$34(A0)` is the menu offset field; the dialogue cursor is `$30(A0)`.

### 7.4 The `001D` entry opcode ⚠ **new — resolves rev-3 §11 item 4**

The event bytecode in the head region (before the text region) contains a
**`001D <16-bit offset>`** instruction: "start dialogue at offset".

| File       | `001D` sites in head | Operand lands on `$2100` |
| ---------- | -------------------- | ------------------------ |
| `ADV_01.D` | 203                  | **203 / 203 (100%)**     |
| `ADV_02.D` | 80                   | 79 / 80                  |

Every operand points at a `$2100` portrait word, and `target-2` is `$2323`
(194×) or `$0D0A` (9×). Zero false positives — the opcode is a perfect filter.

⚠ **The entry points at block start + 2**, i.e. past the `$2323`. A naive search
for block starts finds nothing and wrongly suggests dialogue is unaddressed.

Entries appear consecutively in the event stream, one per dialogue box:

```
0x59A: 001D 3840    0x5A2: 001D 38AC    0x5AC: 001D 38EC
0x59E: 001D 387A    0x5A6: 001D 38CE
```

203 entry points serve 926 dialogue blocks: ~22% are entered directly, the rest
are reached by `$2424` chaining (§6.2).

### 7.5 Entry seeding

`SRUN_X.P` `0x2396` allocates an object slot (32 objects × `$80` at `$FFD000`,
free slot = bit 6 of byte 0 clear) and returns it in `A1`. The caller passes the
script offset in `D0`:

```
001260   ANDI.L  #$FFFF,D0        ; 16-bit offset
001266   ADDI.L  #$210000,D0      ; + file base
00126C   MOVE.L  D0,$30(A1)       ; seed the running cursor
```

`$30(An)` is a field of that `$80`-byte object struct, alongside `$28` (cursor),
`$34` (menu offset) and `$3C` (output pointer).

⚠ **Consequence:** entry offsets are 16-bit, so every byte of the 65,536-byte
file is reachable as an entry point — **including the tail**. The walk itself is
32-bit. 64 KB therefore remains a hard cap on file size, but not on where text
may live within the file.

---

## 8. Character table

**963 strings, 15,806 full-width glyphs** decoded from `ADV_01.D` with
`KANJI1.K`. 673 distinct indices, 44 unused.

### 8.1 Confirmed error, fixed

**Index 98 is ア, not ァ.** Three independent confirmations: ink bbox
`(1,1)-(13,13)`, the full cell, against 8–10 rows for every genuine small kana;
the run `98`–`105` then reads ア ィ イ ウ ェ エ ォ オ, strictly increasing in
gojūon order; and the unpatched ITEM-menu screenshot.

**Index 99 is ィ and is correct** — 10 rows of ink to イ's 13, and it lacks
イ's upper-left stroke. Small ァ and ゥ are simply absent from this bank, which
is normal since each bank holds only what its scene uses.

### 8.2 Verification by structure, not frequency

**Frequency is the wrong axis** — it is the axis on which there is no evidence
to be had. Three oracles that do not depend on frequency:

**Sort order.** The banks are sorted (gojūon for kana, on-reading for kanji).
Kana `26`–`162`: monotonic in Unicode order, **0 violations**. Kanji
`163`–`716`: using full reading sets and proper gojūon collation — base kana
first, dakuten as a secondary key — **554 of 554** admit a consistent
non-decreasing reading assignment.

Two apparent violations, both resolved:

| Index | Char | Neighbours  | Resolution               |
| ----- | ---- | ----------- | ------------------------ |
| 521   | 叩    | 択 たく → 達 たつ | sorted under **kun** たたく |
| 670   | 戻    | 目 もく → 問 もん | sorted under **kun** もどる |

So the bank sorts by on-reading, **falling back to kun for kanji that are
effectively kun-only in use.** Worth knowing before writing the bank-differ.

**Pixel match.** Each real bitmap correlated against renders of all 717 claimed
characters. **529 come out rank 1.** The test degrades on complex kanji at
16×14 (願, 議, 頭 become mush), so a poor rank is weak evidence of error, but
rank 1 is strong evidence of correctness.

**Kana ink size.** Small kana paired against their large counterparts and
measured. This is what caught index 98 mechanically.

**Result: all 717 entries are confirmed by at least one oracle.** The list
worth eyes is the 26 pixel-weak indices occurring 0–1 times, in
`handcheck.txt`, rarest first — down from 392.

### 8.3 Not an error

Indices `6` (ー) and `179` (一) have **byte-identical bitmaps**. Correct — they
are indistinguishable at 16×14 and told apart by position alone. The bank-differ
will need a tiebreaker for this pair.

---

## 9. English insertion ✅ **confirmed in menus and dialogue**

### 9.1 The substitution rule

**One original cell = one word = two Latin characters.** Replace word-for-word
and the file length, line count, `$0D0A` positions, block headers and every
offset stay identical. This remains the safest model; §9.7 is the alternative
when the budget will not stretch.

### 9.2 The high-bit encoding — **required for dialogue**

Because the main CPU tests the sign bit (§5.5), plain ASCII pairs are not text.
Encode **each Latin byte as `ASCII | $80`**, so every pair is ≥ `$A0A0`:

|                                           |                                      |
| ----------------------------------------- | ------------------------------------ |
| Main CPU `BMI`                            | bit 15 set → **text path**           |
| Sub CPU `CMPI.W #$9A00 / BCC`             | ≥ `$9A00` → **half-width path**      |
| `ANDI.L #$FF` per byte                    | indexes `FONT86` slot `ASCII \| $80` |
| Reserved high bytes `$0D/$21/$23/$24/$63` | **unreachable** — every byte ≥ `$A0` |

So the only supporting change is a font rebuild: mirror the 95 glyphs from
`$20`–`$7E` into `$A0`–`$FE` (`hifont.py`). **No engine patch.**

**There are no reserved characters.** Note that `$63` is lowercase `c` — under
plain ASCII it would have become a reserved first character, which the high-bit
encoding avoids rather than has to work around.

**Cost:** the mirrored range displaces the half-width **katakana** at
`$A1`–`$DF`. Any menu still showing stock katakana renders as Latin garbage.
For a finished English patch those are translated anyway. Full-width menu items
drawn from `KANJI*.K` are unaffected, which is why untranslated menus still
render correctly alongside a hi-font dialogue patch.

### 9.3 In-game results

| Test                                                           | Result                                             |
| -------------------------------------------------------------- | -------------------------------------------------- |
| Menus, plain ASCII (`LOOK`/`TALK`/`ITEM`, `AROUND`, `BARKEEP`) | ✅                                                  |
| Full UI translation, 44 lines                                  | ✅                                                  |
| Mixed full-width + half-width on one line                      | ✅ correct baseline                                 |
| Odd-length line, padded                                        | ✅ no stray glyph                                   |
| Punctuation, stock `FONT86.G`                                  | ❌ renders as kanji, as predicted                   |
| Punctuation, `FONT86_en.G`                                     | ✅                                                  |
| **Dialogue, plain ASCII**                                      | ❌ **no window** — §5.5                             |
| **Dialogue, high-bit + `FONT86_hi.G`**                         | ✅ **`Same old Silver Moon.` / `Everyone's here.`** |
| **Dialogue, Japanese–English–Japanese sandwich**               | ✅ **`マオと何Mid Eng している`**                           |
| Mixed case, lowercase descenders                               | ✅                                                  |
| ⚠ **Relocated + expanded block, 22 → 48 cells**                | ✅ **all three 16-cell lines, §9.7**                |

### 9.4 Font rebuilds

- `mkfont86.py` → `FONT86_en.G`. Fills ASCII **punctuation** slots
  `0x21`–`0x2F`, `0x3A`–`0x40`, `0x5B`–`0x60`, `0x7B`–`0x7E` (or `--minimal`
  for `. , ' - ? ! : ( ) "`). Needed because every ASCII punctuation slot holds
  a kanji. Displaces those kanji, which is a live risk on status/equipment
  screens (§11 item 1). Also the place to redraw lowercase `g` (§3.2).
- `hifont.py` → `FONT86_hi.G`. Mirrors `$20`–`$7E` into `$A0`–`$FE`. **Run it
  on `FONT86_en.G`, not on stock**, so the punctuation comes along.

### 9.5 Budgets ⚠ **revised**

Under strict word-for-word substitution the budget is a flat 2:1 — two Latin
characters per Japanese cell — where Japanese→English expansion is typically
more than 2×.

|               | p25   | median    | p90   | max    |
| ------------- | ----- | --------- | ----- | ------ |
| per **line**  | 10 ch | **16 ch** | 24 ch | 32 ch  |
| per **block** | 22 ch | **34 ch** | 50 ch | 180 ch |

⚠ **The 2:1 figure is a property of the substitution model, not of the file.**
Counting words with bit 15 set across the text region, and adding tail slack
(§7.2) as available cells:

| File       | Text cells | EN @ 2:1 | With tail  | Ratio      |
| ---------- | ---------- | -------- | ---------- | ---------- |
| `ADV_01.D` | 15,853     | 31,706   | **42,562** | **2.68:1** |
| `ADV_02.D` | 10,148     | 20,296   | **50,968** | **5.02:1** |

(`ADV_01`'s 15,853 against §6.1's 15,838 is a 15-word parser difference, not
material.)

⚠ **Screen space is not the binding constraint.** The window holds 3 rows ×
16 cells = 48 cells = 96 English characters, and the median block is 34
characters. Typical dialogue uses about a third of the available box. This was
a storage problem, and §7.2 supplies the storage.

### 9.6 UI translation

44 lines, 450 bytes, length unchanged. Block map:

| Block             | Header   | Lines × cells | Contents                                           |
| ----------------- | -------- | ------------- | -------------------------------------------------- |
| Main menu         | `0x33D4` | 6 × 5         | LOOK / TALK / MOVE / ITEM / CONTACT                |
| MOVE destinations | `0x341E` | 15 × 6        | + a 16th entry at `0x34F2`                         |
| ITEM              | `0x3500` | 1 × 5         | ポケットセクレタリー                                         |
| CONTACT list      | `0x350E` | 5 × 6         | Nat / DataNet / Tookadou / Triple Z / Angel Clinic |
| Yes / No          | `0x3556` | 2 × 3         | はい / いいえ                                           |
| LOOK submenu      | `0x37A6` | 2 × 4         | 店内 / バーテン                                          |
| TALK submenu      | `0x37BC` | 3 × 4         | 仲間 / バーテン / ハジメ                                    |
| DataNet search    | `0x37DC` | 3 × 6         |                                                    |
| Prompt            | `0x3808` | 1 × 7         | 選択して下さい                                            |
| Choice            | `0x381A` | 2 × 8         | 真相を明かす / 明かさない                                     |
| Pause menu        | `0xD572` | 2 × 3         | セーブ / メッセージ                                        |
| Message speed     | `0xD584` | 3 × 2         | 遅い / 普通 / 速い                                       |

The headerless entry at `0x34F2` is **explained**: `0x341E` carries `CNT = 15`
and ends after 15 lines; `0x34F2` is a separate block whose control run is the
bare half-width text with no `CNT`. Not a missing header.

Menus are **context-filtered**: the bar counter offers only LOOK/TALK/ITEM until
the scene advances, and the LOOK submenu swaps rows as the scene progresses. An
unpatched-looking menu is usually a filtered row, not a failure.

Unlike dialogue, menu blocks **are** reached by 16-bit offsets embedded in the
event bytecode (§7.3), so they cannot be relocated without finding and updating
every one. 29 of 41 `count` blocks in `ADV_01` have at least one such
reference.

### 9.7 Relocation and expansion ✅ **confirmed in-game** ⚠ **new**

A `$2323`-terminated dialogue block can be **moved into the tail and made
longer than its original cell count**. Procedure:

1. Locate the block's `001D` operand in the event bytecode (§7.4).
2. Write the new block at the tail start: portrait run, then lines, each
   `$0D0A`-terminated, then a `$2323` terminator matching the original.
3. Rewrite the `001D` operand to the new offset.

The original block may be left in place and orphaned — the edit is then two
bytes outside the tail and the file size never changes.

**Test performed on `ADV_01.D`:** block `0x3840` (portrait `$00`, `$63C8`,
13-cell and 9-cell lines = 22 cells / 44 English characters) relocated to
`0xD598` and expanded to three 16-cell lines = 48 cells / **96 English
characters**, with the single `001D` operand at head `0x59C` changed from
`3840` to `D598`.

**Result: all three lines rendered, portrait intact, window auto-sized to three
rows, no side effects.** Confirms simultaneously that the tail is usable, that
entry repointing works, that the walk follows a longer block, and that the
window geometry follows the main-CPU cursor rather than any stored extent.

Constraints:

- Only `$2323`-terminated blocks. `$2424`-chained blocks must stay contiguous
  (§6.2).
- Terminate the relocated block, or the walk consumes tail zeros forever (§7.2).
- 16 cells per line, 3–4 rows per window; paginate with `$2424` beyond that.
- The file cannot exceed 65,536 bytes (§7.5).

---

## 10. Font banks

| Bank                            | Size   | Glyphs | Capacity | Free |
| ------------------------------- | ------ | ------ | -------- | ---- |
| `KANJI0.K`                      | 32,768 | 835    | 1,170    | 335  |
| `KANJI1.K`                      | 32,768 | 717    | 1,170    | 453  |
| `KANJI2.K`                      | 32,768 | 765    | 1,170    | 405  |
| `KANJI3.K`                      | 32,768 | 911    | 1,170    | 259  |
| `KANJI4.K`                      | 32,768 | 827    | 1,170    | 343  |
| `KANJI5.K`                      | 32,768 | 850    | 1,170    | 320  |
| `KANJI6.K`                      | 32,768 | 960    | 1,170    | 210  |
| `KANJI7.K`                      | 32,768 | 998    | 1,170    | 172  |
| `KANJI8.K` = `KANJI9.K`         | 45,056 | 1,532  | 1,609    | 77   |
| `MSG_01.K` = `05` = `06` = `07` | 24,512 | 697    | 875      | 178  |
| `MSG_02.K`                      | 24,512 | 675    | 875      | 200  |
| `MSG_03.K`                      | 24,512 | 788    | 875      | 87   |
| `MSG_04.K`                      | 24,512 | 771    | 875      | 104  |
| `TMSG01.K`                      | 24,512 | 248    | 875      | 627  |
| `XMSG01.K`                      | 24,512 | 113    | 875      | 762  |
| `BMSG01.K`                      | 24,512 | 160    | 875      | 715  |

**Duplicate files are intentional** — standard Sega CD practice, the same file
written to several places so it sits near whatever loads with it.

### 10.1 Bank ↔ text pairing

**`ADV_NN.D` uses `KANJI_NN.K`.** Each bank contains exactly what its scene
needs: `ADV_01.D` max code 716 ↔ `KANJI1.K` 717 glyphs; `ADV_02.D` max 764 ↔
`KANJI2.K` 765.

### 10.2 Bank sort order

| Range   | Contents                                            |
| ------- | --------------------------------------------------- |
| 0       | Full-width space                                    |
| 1–10    | `、 ・ ？ ！ 々 ー 〜 … 『 』`                               |
| 11–20   | Digits `0`–`9`                                      |
| 21–25   | Letters `C D O R Z` only                            |
| 26–97   | Hiragana (gojūon, incl. small kana and dakuten)     |
| 98–162  | Katakana (index 98 = **ア**)                         |
| 163–716 | Kanji, by on-reading, kun where on is unused (§8.2) |

Only five Latin letters exist in the full-width banks, which is why English
goes through `FONT86.G`.

Because the sort is shared, glyph bitmaps can be diffed between banks to carry
character-table entries across automatically.

---

## 11. Open questions

1. **Displaced kanji on status/equipment screens** (§9.4). `FONT86.G` is
   global; nothing tested so far exercises those screens, and the high-bit
   rebuild displaces the katakana range as well. **The only unverified risk that
   could invalidate finished translation work.**
2. **The 69 WIN-preceded blocks with no literal `001D`** (§6.2). Computed
   offsets, or another call path? Must be resolved before bulk relocation.
3. **Header entries `[0]`–`[4]`, `[6]`, `[7]`** (§7.0). Only `[5]` is
   identified.
4. **`$80058` → `$0141A0`** (§5.4). A main-CPU parameter the dialogue loop
   copies before drawing. It sits adjacent to `$80054` in the mailbox and is a
   candidate wrap width.
5. **Portrait ID → character mapping.** `$00` = Rokudou confirmed. 27 IDs
   remain; `$0001`/`$0201`/`$0202`/`$0203` are probably expression or pose
   variants of the same four party members.
6. **Which bank pairs with `BTL_*.D`.** `BMSG01.K` has 160 glyphs and
   `BTL_10.D` uses 146 distinct codes — a tight fit, though `BTL_10.D`'s max
   code of 713 argues against direct indexing.
7. **Whether the loader honours the ISO extent** (§5.6). The filename table
   carries no size field. If loads are sized from the directory record rather
   than a hardcoded 64 KB read, the file-size cap in §7.5 may be softer than
   assumed. Untested and speculative.
8. **`WARNING.MSG`** (65,024 B), **`TMSG01.K` / `XMSG01.K`**, **`O_ASCI.G`** —
   unexamined.
9. **The `SRUN_M.PRG` `MULU #28` sites** (§2) — glyph indexing or unrelated
   record stride?

**Resolved since revision 3:** ~~the `$34(A0)` text-offset source~~ (§7.3–7.5);
~~can `$0D0A` be moved within a block~~ (moot — but reflow *is* live, since the
column carries into the row by design, §5.5); ~~`$63C8`/`$63F8` uncatalogued~~
(§5.5); ~~the headerless list entry at `0x34F2`~~ (§9.6).

---

## 12. Toolchain

See `README.md` for usage. Summary:

| File                                                | Purpose                                                                                           |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `srblocks.py`                                       | Block-level extractor. `blocks` / `sheet` / `counts` / `verify`. `--en` decodes high-bit English. |
| `hwpatch.py`                                        | Word-for-word English, **plain ASCII** — menus only                                               |
| `hipatch.py`                                        | Word-for-word English, **high-bit** — works everywhere                                            |
| `relocate.py`                                       | ⚠ **New.** Relocate a `$2323` block into the tail, expand it, repoint its `001D` (§9.7)           |
| `tailpatch.py`                                      | Original glyphs then ASCII mid-line, for probes                                                   |
| `blockpatch.py`                                     | Whole-block rewrite with movable `$0D0A`. Useful for menus and for in-block reflow                |
| `binpatch.py`                                       | Splice a file into a disc image; recomputes EDC/ECC                                               |
| `mkfont86.py`                                       | Rebuild `FONT86.G` with Latin punctuation                                                         |
| `hifont.py`                                         | Mirror `$20`–`$7E` → `$A0`–`$FE` for the high-bit encoding                                        |
| `preview.py`                                        | Render patched blocks exactly as the renderer will                                                |
| `m68kdis.py`                                        | 68k disassembler wrapper (capstone)                                                               |
| `audit_table.py`, `verify_glyphs.py`, `priority.py` | Character-table verification                                                                      |
| `atlasx.py`, `collate.py`, `hwmap.py`, `mkhwmap.py` | Support modules                                                                                   |
| `kanji1_table_v2.py`                                | Corrected `KANJI1.K` table with occurrence counts                                                 |

### 12.1 Suggested next steps

1. Change `srblocks.find_region` to read header `[5]` (§7.1).
2. Resolve open question 2 — the 69 unaddressed WIN blocks.
3. Header-dump `ADV_03`–`ADV_11` and `BTL_*` to confirm the layout generalises
   and total the slack across the disc.
4. Exercise the status and equipment screens against the rebuilt fonts
   (open question 1).
5. Write the bank-differ. All banks share sort order, so matching bitmaps
   between `KANJI1.K` and `KANJI2.K` carries most of the 717 known characters
   across, leaving only new glyphs to identify by hand.
6. Translate. `adv01_blocks.tsv` has an empty `english` column, with speaker ID
   and per-line budget as context — but per §9.5 and §9.7 the per-line budget is
   now a starting point, not a ceiling.

---

## 13. Legal note

The extracted script is copyrighted material belonging to the rights holders.
Keep dumps private and distribute any release as a **patch**, never as game
files or extracted script data.
