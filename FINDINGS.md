# Shadowrun (Sega CD, JP) — Text Format Findings

Reverse-engineering notes for a Japanese→English translation patch.

**Status: format fully solved. English confirmed in-game in both menus and
dialogue, word-for-word, with no engine patch.** The remaining work is
per-bank character tables and the translation itself.

> **Revision 3.** Supersedes revision 2. The largest change is §4/§5: the
> **main CPU**, not the sub CPU, is what decides whether a word is text, and it
> uses the **sign bit**. That single fact explains why half-width English
> worked in menus and silently failed in dialogue for six test builds. The fix
> is a font rebuild, not a code patch (§9.2). Sections marked ⚠ contain
> corrections to revision 2.

---

## 1. Summary

| Question | Answer |
|---|---|
| Is the text compressed? | **No.** Uncompressed throughout. |
| Pointer table to rebuild? | No absolute table. Strings are reached by a 16-bit offset into the loaded file (§7.3). |
| Where is the script? | `ADV_*.D` (dialogue) and `BTL_*.D` (battle) |
| Encoding | Big-endian 16-bit, one word = one screen cell |
| Text vs control | ⚠ **The main CPU tests the SIGN BIT** (§5.5). `$8000`–`$FFFF` = text; below = control code. |
| Full-width glyph | `$8000`–`$99FF`, index = `value & $7FFF` |
| Half-width pair | `$9A00`–`$FFFF`, two glyphs, high byte then low |
| English encoding | ⚠ **`ASCII \| $80` per byte**, so every pair is ≥ `$A0A0` (§9.2) |
| Font (full-width) | 16×14 px, 1bpp, column-major, 28 B/glyph — `KANJI*.K` at `$054000` |
| Font (half-width) | 8×16 px, 1bpp, 16 B/glyph — `FONT86.G` at `$05C000`, indexed at true ASCII |
| Font↔text pairing | `ADV_NN.D` ↔ `KANJI_NN.K` |
| Renderers | Sub CPU `SRUN_S.PRG` (load base `$00010000`); interpreter in `SRUN_X.P` / `COM_*.P` / `SRUN_M.PRG` (base `$0`) |
| English insertion | **Working in menus and dialogue.** Verified on hardware-accurate emulation. |
| Reserved characters | ⚠ **None**, in the high-bit encoding (§9.2) |
| Script size (est.) | ~150–200k characters across all files |

---

## 2. Disc layout

1,213 files.

| Ext | Files | Bytes | Contents |
|---|---|---|---|
| `.G` | 951 | 48.9 MB | Graphics **and fonts** |
| `.D` | 150 | 135.4 MB | Map, battle, adventure, streamed media |
| `.P` | 42 | 2.0 MB | Main-CPU code overlays |
| `.K` | 33 | 0.9 MB | Full-width font banks |
| `.SD` | 27 | 1.0 MB | Sound driver / PCM |
| `.PRG` | 2 | 64.8 KB | Main + Sub CPU programs |
| `.BIN` | 2 | 8.8 KB | Sega CD IP/SP boot |
| `.MSG` | 1 | 65.0 KB | `WARNING.MSG` (unexamined) |
| `.TXT` | 3 | 61 B | ISO 9660 stubs — ignore |

### Files confirmed to contain no text

- `MAP_*.D` (47 files) — tile/collision data only.
- `DUM_00.D`, `NOT_01..07.D` — 8 files of 16,180,508 bytes (~129 MB). Streamed video/audio.

`COM_10` and `COM_20` are 89.4% identical, so the 42 overlays share a large
common core. ⚠ **That core includes the script interpreter** (§5.5), which
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

```python
byte = data[i*28 + (x // 8) * 14 + y]
set  = (byte >> (7 - (x % 8))) & 1
```

Flat array from offset 0. No header, no compression, no index.

### 3.2 Half-width — `FONT86.G`

8 × 16 px, 1bpp, one byte per row, 16 bytes per glyph, 256 glyphs, 4,096 bytes
exactly. Loaded to `$05C000`. **Indexed at true ASCII / JIS X 0201.**

| Range | Contents |
|---|---|
| `0x20`–`0x7E` | ASCII: space, digits, `A`–`Z`, `a`–`z`, and kanji in the punctuation slots |
| `0x9A`–`0x9E` | ⚠ **semi-voiced** katakana パピプペポ |
| `0xA1`–`0xDF` | half-width katakana, exact JIS order |
| `0xE6`–`0xF4` | ⚠ **voiced** katakana ガギグゲゴザジズゼゾダヂヅデド |
| `0xFA`–`0xFE` | ⚠ **voiced** katakana バビブベボ |
| `0xFF` | ⚠ ヴ |
| `0xE0`–`0xE5`, `0xF6`–`0xF9`, other gaps | status/equipment kanji |

⚠ **Lowercase is present in the stock font**, `a`–`z` at `0x61`–`0x7A`, with
proper descenders. No font work is needed for mixed case.

⚠ **The precomposed slots follow two exact arithmetic rules**, recovered by
bitmap-diffing the font against its own base kana (`mkhwmap.py`):

```
voiced      = base + 0x30      0xB6-0xC4 -> 0xE6-0xF4 ,  0xCA-0xCE -> 0xFA-0xFE
semi-voiced = base + 0xD0      0xCA-0xCE -> 0x9A-0x9E
0xFF        = ヴ  (ウ 0xB3 plus dakuten)
```

Note the semi-voiced block sits **below `0xA1`**, which revision 2 missed.
Corroboration: `0xF5` is one of only four empty slots in the file and lands
exactly at ナ + `0x30`, the first base kana past ト with no voiced form; and all
six shipped half-width runs decode correctly (§4.2).

**Metrics:** caps occupy rows 0–14 (baseline row 14), descenders reach row 15,
ink stays within columns 1–6.

The renderer masks the index with `$FF`, so the file cannot grow. See §9.2 and
§9.4 for the two rebuilds.

### 3.3 Genesis 4bpp tile fonts

Three files use the Genesis 4bpp 8×8 tile format, 32 bytes per tile, on a
**different code path** from `$05C000`. Not involved in dialogue rendering.

| File | Tiles | Used | Indexing | Contents |
|---|---|---|---|---|
| `ASCII.G` | 96 | 96 | **from 0** (`0x20` → tile 0) | ASCII `0x20`–`0x7F` |
| `FONT_8.G` | 256 | 224 | true ASCII | ASCII + half-width katakana |
| `FONTS8.G` | 256 | 128 | true ASCII | ASCII only, bolder |

The indexing difference is a trap: mixing them up shifts text by 32 tiles.
`O_ASCI.G` (2,048 B) remains unexamined.

---

## 4. Text encoding ⚠ **corrected**

Big-endian 16-bit stream. **One word = one screen cell.**

| Value | Meaning |
|---|---|
| `$8000`–`$99FF` | one full-width glyph, index = `value & $7FFF`, from `$054000` |
| `$9A00`–`$FFFF` | two half-width glyphs from `$05C000`, high byte then low |
| `$0D0A` | end of line |
| below `$8000` | **control code** — consumed by the main CPU (§5.5) |

Revision 1 said "below `$8000` = control code"; revision 2 overruled it to
"anything outside the full-width window = half-width text". ⚠ **Revision 1 was
right about the main CPU and revision 2 was right about the sub CPU.** Both
statements are true of different processors, and the main CPU runs first, so
its rule governs. See §5.5.

`$8000` (index 0) is a full-width space.

### 4.2 Shipped half-width text

`ADV_01.D` contains six half-width runs, all whole lines:

| Offset | Text | Block kind |
|---|---|---|
| `0x003420` | シルバームーン | count |
| `0x003490` | オンフォール | count |
| `0x0034F2` | エンジェルクリニック | page (§9.6) |
| `0x003502` | ポケットセクレタリー | count |
| `0x003548` | エンジェルクリニック | count |
| `0x00D57C` | メッセージ | count |

⚠ **Five of six are in count (menu) blocks, and none of the 927 dialogue
blocks contains any half-width text at all.** That distribution is the
fingerprint of §5.5: the shipped game only ever puts half-width text where the
main-CPU interpreter is not the thing driving the draw.

---

## 5. The renderers

Text rendering is split. The **main CPU** walks the script and decides what is
text; the **sub CPU** turns text words into pixels. Revision 2 treated the sub
CPU as authoritative. It is not.

Load base for `SRUN_S.PRG` is `$00010000`. `SRUN_X.P`, `COM_*.P` and
`SRUN_M.PRG` are at base `$0` (file offset = address).

### 5.1 Full-width glyph fetch (sub CPU)

Three near-identical routines at `$0112D2`, `$0113F0`, `$01167E`:

```asm
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

```asm
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

### 5.3 Output footprint — equal on both paths ✅ **verified at both dispatchers**

Full-width (`$011366`, `$0116FA`) writes 16 rows of 4 bytes via `(A3)+` plus a
right-hand strip at `$40(A3)`, then `ADDA.L #$40,A3` — **128 bytes**.
Half-width (`$0113A6`, `$011728`) writes 16 rows of 4 bytes per glyph, twice —
**128 bytes**. Same byte layout.

**One source word occupies the same buffer footprint either way**, so
word-for-word substitution never disturbs geometry.

### 5.4 The three draw loops ⚠ **corrected**

Only three dispatcher call sites exist in `SRUN_S.PRG`:

```
$011590  BSR.W $01167E   <- loop $01153C   DIALOGUE
$0115E4  BSR.W $0112D2   <- loop $0115A2   menu, $08xxxx mailbox
$01165C  BSR.W $0112D2   <- loop $0115FE   menu, $0Cxxxx mirror
$01179A  BSR.W $0117AA   <- atlas/debug dump
```

⚠ **Only the two menu loops count cells and lines.** `$01153C` writes neither
`$8000A` nor `$8000C`. Revision 2's §6.1 read the dynamic counting as the
general mechanism; it is menu-only, and dialogue window geometry does not come
from the sub CPU at all.

The menu loop:

```asm
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

```asm
01154C   MOVEA.L $80054,A1
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

⚠ Two consequences. There is **no half-width filter** — the sub CPU renders
half-width in dialogue perfectly well. And **`$0D0A` is discarded**: consumed,
`A3` not advanced, no row break emitted. Visual line breaks in dialogue are
produced upstream, by the main CPU's cursor.

### 5.5 The main-CPU script interpreter ⚠ **new, and the key to everything**

`SRUN_X.P` `0x1342` (also at `0x405E`, `COM_10.P` `0x1268`, `SRUN_M.PRG`
`0x196A` — byte-identical `3019 6B00 003E 3200 E049 0C01 0021`):

```asm
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
```

**The main CPU classifies text by bit 15, not by the `$8000`–`$99FF` window.**
A plain ASCII pair such as `$5361` ("Sa") has bit 15 clear, so it falls into
the control-code dispatcher, matches nothing, and is eaten at `001374`.

The interpreter keeps a cursor in `$28(A0)`: a **4-bit column counter in bits
7–10** and a **2-bit row counter in bits 11–12**. The newline handler only
advances the row when the column is non-zero:

```asm
00142C   MOVE.L  A1,$30(A0)
001430   MOVE.W  $28(A0),D0
001434   ANDI.W  #$780,D0
001438   BEQ.W   $1336          ; column still zero -> no row advance
00143C   ANDI.W  #$1800,$28(A0)
001442   ADDI.W  #$800,$28(A0)  ; bump row
```

The 4-bit column is consistent with the file-wide maximum of 16 cells per line,
and the 2-bit row with a 3-line dialogue window.

**This is the whole of the failure that took six test builds to isolate.** The
sub CPU drew the English into the buffer — it was visible on screen — but the
main CPU's cursor never advanced across it, so window geometry and DMA extent
were computed as though those cells did not exist. Text after the English was
truncated, and a line that *began* with English produced a zero-width window
and therefore no box at all.

⚠ **`$63xx` decoded** (revision 2 §11.2 item 6): takes the low byte, shifts
right 4, stores to `$FFC3BC`. So `$63C8` → 12 and `$63F8` → 15.

### 5.6 File loading

`SRUN_S.PRG` holds a filename table of 1,170 fixed 8-byte records at `$011B38`
(file `0x1B38`–`0x3FC8`). `FONT86.G` is index **347 (`$15B`)**.

Main-CPU code requests a file through a mailbox in work RAM:

```asm
MOVE.W  #index,$FFC354
MOVE.W  #mode,$FFC356      ; 0 = raw, 1 = seen on .G font loads
MOVE.L  #dest,$FFC358
BSET.B  #0,$FFC352
```

Destinations: `$03xxxx`–`$07xxxx` = sub PRG RAM, `$09xxxx`/`$0Bxxxx` = sub Word
RAM. Known loads: `ADV_NN.D` → `$090000`, `STATUS.G` → `$04E000`, `SPELL0.G` →
`$068000`, `FONTS8.G` → `$042000`. The `FONT86.G` load site has not been found;
academic, since the font is demonstrably resident.

---

## 6. Script grammar ✅ **closed**

`srblocks.py verify` accounts for **every word** of `ADV_01.D`'s text region,
`0x33A4`–`0xD598`, 20,730 words, zero unclaimed.

A control run occurs only at a line start (immediately after `$0D0A`, or at the
region start) and is any non-empty subset of the following, **in this fixed
order**:

| Slot | Values | Meaning |
|---|---|---|
| `WIN` | `$2323` \| `$2424` | window / page control |
| `CNT` | `$0001`–`$001F` | line-count header |
| `PORTRAIT` | `$2100` + 2 words | speaker portrait |
| `EXTRA` | `$63C8` \| `$63F8` | parameter 12 / 15 (§5.5) |

⚠ Two corrections to revision 2:

- `WIN` and `CNT` **co-occur** (`2323 0002`, `2323 0005`, …, 11 sites). The
  "two framings coexist" reading was one grammar with an optional `CNT` slot.
- The portrait ID is a **full word, not `[id]00`**. `$0201`, `$0202`, `$0203`
  and `$0001` all occur. **28** distinct speaker words, not 24.

### 6.1 Block types

| Kind | Definition | Count in `ADV_01.D` |
|---|---|---|
| `count` | run contains `CNT`; exactly `CNT` lines follow; self-delimiting | 41 (menus) |
| `page` | no `CNT`; lines run to the next control run | 927 (dialogue) |

**968 blocks, 2,124 lines, 15,838 cells.** Block shapes: 221 × 1 line,
364 × 2, 372 × 3, 11 × 4+.

Speaker frequency: `0000` ×145, `0200` ×131, `0100` ×59, `1100` ×50, `0300` ×31,
then a long tail. ✅ **Portrait `$00` is Rokudou**, confirmed in-game — his face
leaves the party strip when the portrait rises.

---

## 7. Locating text within a `.D` file

### 7.1 Region bounds

`0x33A4`–`0xD598` for `ADV_01.D`. ⚠ Region detection must accept **half-width
cells**, not just full-width: a translated file has English on the very first
line, and a full-width-only backward walk starts 11 words late and silently
drops block 0. Fixed in `srblocks.find_region`.

### 7.2 False positives

A naive scan for `$8000`–`$82CC` picks up ordinary 68k data; `$8000`, `$8004`
and `$800C` are common in address-register indexed modes. The distinction is
statistical — real Japanese is kana-dense, binary noise is not.

### 7.3 String addressing

`SRUN_X.P` `0x1FA0` writes a 16-bit offset to `$20000E`; the sub CPU adds it to
the `$090000` buffer base and reads the text in place. `ADV_*.D` files are
exactly 65,536 bytes, so 16 bits addresses the whole file.

```asm
001FA0   MOVE.W  $34(A0),$20000E
001FA8   MOVE.L  #$0D0000,$200006
001FB2   BSET    #1,$200000
001FBE   MOVE.W  $20000A,$FFCD8E    ; cell count readback
001FC8   MOVE.W  $20000C,$FFCD90    ; line count readback
001FE8   MULU.W  D2,D1
001FEA   LSL.W   #6,D1              ; DMA length, in WORDS
```

⚠ This path is **menus only** (`BSET #1`). Dialogue uses a different kick and
does not read those counts back.

The offset comes from `$34(A0)`, a struct field whose source has not been
traced. Word-for-word substitution sidesteps the question entirely.

---

## 8. Character table

**963 strings, 15,806 full-width glyphs** decoded from `ADV_01.D` with
`KANJI1.K`. 673 distinct indices, 44 unused.

### 8.1 Confirmed error, fixed

⚠ **Index 98 is ア, not ァ.** Three independent confirmations: ink bbox
`(1,1)-(13,13)`, the full cell, against 8–10 rows for every genuine small kana;
the run `98`–`105` then reads ア ィ イ ウ ェ エ ォ オ, strictly increasing in
gojūon order; and the unpatched ITEM-menu screenshot.

**Index 99 is ィ and is correct** — 10 rows of ink to イ's 13, and it lacks
イ's upper-left stroke. Small ァ and ゥ are simply absent from this bank, which
is normal since each bank holds only what its scene uses.

### 8.2 Verification by structure, not frequency

Revision 2 recommended hand-checking every index occurring fewer than ~5 times.
That is 392 indices, 183 of them occurring exactly once. **Frequency is the
wrong axis** — it is the axis on which there is no evidence to be had.

Three oracles that do not depend on frequency:

**Sort order.** The banks are sorted (gojūon for kana, on-reading for kanji),
which makes the ordering a checkable constraint. Kana `26`–`162`: monotonic in
Unicode order, **0 violations**. Kanji `163`–`716`: using full reading sets and
proper gojūon collation — base kana first, dakuten as a secondary key, which is
the collation Japanese dictionaries actually use — **554 of 554** admit a
consistent non-decreasing reading assignment.

Two apparent violations, both resolved rather than left open:

| Index | Char | Neighbours | Resolution |
|---|---|---|---|
| 521 | 叩 | 択 たく → 達 たつ | sorted under **kun** たたく |
| 670 | 戻 | 目 もく → 問 もん | sorted under **kun** もどる |

⚠ So the bank sorts by on-reading, **falling back to kun for kanji that are
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
offset stay identical.

### 9.2 The high-bit encoding ⚠ **required for dialogue**

Because the main CPU tests the sign bit (§5.5), plain ASCII pairs are not text.
Encode **each Latin byte as `ASCII | $80`**, so every pair is ≥ `$A0A0`:

| | |
|---|---|
| Main CPU `BMI` | bit 15 set → **text path** |
| Sub CPU `CMPI.W #$9A00 / BCC` | ≥ `$9A00` → **half-width path** |
| `ANDI.L #$FF` per byte | indexes `FONT86` slot `ASCII \| $80` |
| Reserved high bytes `$0D/$21/$23/$24/$63` | **unreachable** — every byte ≥ `$A0` |

So the only supporting change is a font rebuild: mirror the 95 glyphs from
`$20`–`$7E` into `$A0`–`$FE` (`hifont.py`). **No engine patch.**

⚠ This retires the parity restriction of revision 2 §9.5 completely. **There
are no reserved characters.** Note that `$63` is lowercase `c` — under plain
ASCII it would have become a reserved first character, which the high-bit
encoding avoids rather than has to work around.

**Cost:** the mirrored range displaces the half-width **katakana** at
`$A1`–`$DF`. Any menu still showing stock katakana renders as Latin garbage.
For a finished English patch those are translated anyway.

### 9.3 In-game results

| Test | Result |
|---|---|
| Menus, plain ASCII (`LOOK`/`TALK`/`ITEM`, `AROUND`, `BARKEEP`) | ✅ |
| Full UI translation, 44 lines | ✅ |
| Mixed full-width + half-width on one line | ✅ correct baseline |
| Odd-length line, padded | ✅ no stray glyph |
| Punctuation, stock `FONT86.G` | ❌ renders as kanji, as predicted |
| Punctuation, `FONT86_en.G` | ✅ |
| **Dialogue, plain ASCII** | ❌ **no window** — §5.5 |
| **Dialogue, high-bit + `FONT86_hi.G`** | ✅ **`Same old Silver Moon.` / `Everyone's here.`** |
| **Dialogue, Japanese–English–Japanese sandwich** | ✅ **`マオと何Mid Eng している`** |
| Mixed case, lowercase descenders | ✅ |

The sandwich is the decisive one: full-width and half-width now both take the
main CPU's text path, so the cursor advances across the English and the
trailing Japanese returns.

### 9.4 Font rebuilds

Two, for two purposes:

- `mkfont86.py` → `FONT86_en.G`. Fills ASCII **punctuation** slots
  `0x21`–`0x2F`, `0x3A`–`0x40`, `0x5B`–`0x60`, `0x7B`–`0x7E` (or `--minimal`
  for `. , ' - ? ! : ( ) "`). Needed because every ASCII punctuation slot holds
  a kanji. Displaces those kanji, which is a live risk on status/equipment
  screens (§11 item 2).
- `hifont.py` → `FONT86_hi.G`. Mirrors `$20`–`$7E` into `$A0`–`$FE`. **Run it
  on `FONT86_en.G`, not on stock**, so the punctuation comes along.

### 9.5 Budgets

Measured across `ADV_01.D`: 2,124 lines, 15,838 cells.

| | p25 | median | p90 | max |
|---|---|---|---|---|
| per **line** | 10 ch | **16 ch** | 24 ch | 32 ch |
| per **block** | 22 ch | **34 ch** | 50 ch | 180 ch |

31.3% of lines give under 12 English characters; 9.1% of blocks do. File-wide
that is 31,676 English characters for 15,838 Japanese — a flat 2:1, where
Japanese→English expansion is typically more than 2×. UI strings fit
comfortably because they are nouns. Dialogue will be tight.

### 9.6 UI translation

44 lines, 450 bytes, length unchanged. Block map:

| Block | Header | Lines × cells | Contents |
|---|---|---|---|
| Main menu | `0x33D4` | 6 × 5 | LOOK / TALK / MOVE / ITEM / CONTACT |
| MOVE destinations | `0x341E` | 15 × 6 | + a 16th entry at `0x34F2` |
| ITEM | `0x3500` | 1 × 5 | ポケットセクレタリー |
| CONTACT list | `0x350E` | 5 × 6 | Nat / DataNet / Tookadou / Triple Z / Angel Clinic |
| Yes / No | `0x3556` | 2 × 3 | はい / いいえ |
| LOOK submenu | `0x37A6` | 2 × 4 | 店内 / バーテン |
| TALK submenu | `0x37BC` | 3 × 4 | 仲間 / バーテン / ハジメ |
| DataNet search | `0x37DC` | 3 × 6 | |
| Prompt | `0x3808` | 1 × 7 | 選択して下さい |
| Choice | `0x381A` | 2 × 8 | 真相を明かす / 明かさない |
| Pause menu | `0xD572` | 2 × 3 | セーブ / メッセージ |
| Message speed | `0xD584` | 3 × 2 | 遅い / 普通 / 速い |

⚠ The headerless entry at `0x34F2` is **explained**: `0x341E` carries `CNT = 15`
and ends after 15 lines; `0x34F2` is a separate block whose control run is the
bare half-width text with no `CNT`. Not a missing header.

Menus are **context-filtered**: the bar counter offers only LOOK/TALK/ITEM until
the scene advances, and the LOOK submenu swaps rows as the scene progresses. An
unpatched-looking menu is usually a filtered row, not a failure.

---

## 10. Font banks

| Bank | Size | Glyphs | Capacity | Free |
|---|---|---|---|---|
| `KANJI0.K` | 32,768 | 835 | 1,170 | 335 |
| `KANJI1.K` | 32,768 | 717 | 1,170 | 453 |
| `KANJI2.K` | 32,768 | 765 | 1,170 | 405 |
| `KANJI3.K` | 32,768 | 911 | 1,170 | 259 |
| `KANJI4.K` | 32,768 | 827 | 1,170 | 343 |
| `KANJI5.K` | 32,768 | 850 | 1,170 | 320 |
| `KANJI6.K` | 32,768 | 960 | 1,170 | 210 |
| `KANJI7.K` | 32,768 | 998 | 1,170 | 172 |
| `KANJI8.K` = `KANJI9.K` | 45,056 | 1,532 | 1,609 | 77 |
| `MSG_01.K` = `05` = `06` = `07` | 24,512 | 697 | 875 | 178 |
| `MSG_02.K` | 24,512 | 675 | 875 | 200 |
| `MSG_03.K` | 24,512 | 788 | 875 | 87 |
| `MSG_04.K` | 24,512 | 771 | 875 | 104 |
| `TMSG01.K` | 24,512 | 248 | 875 | 627 |
| `XMSG01.K` | 24,512 | 113 | 875 | 762 |
| `BMSG01.K` | 24,512 | 160 | 875 | 715 |

**Duplicate files are intentional** — standard Sega CD practice, the same file
written to several places so it sits near whatever loads with it.

### 10.1 Bank ↔ text pairing

**`ADV_NN.D` uses `KANJI_NN.K`.** Each bank contains exactly what its scene
needs: `ADV_01.D` max code 716 ↔ `KANJI1.K` 717 glyphs; `ADV_02.D` max 764 ↔
`KANJI2.K` 765.

### 10.2 Bank sort order

| Range | Contents |
|---|---|
| 0 | Full-width space |
| 1–10 | `、 ・ ？ ！ 々 ー 〜 … 『 』` |
| 11–20 | Digits `0`–`9` |
| 21–25 | Letters `C D O R Z` only |
| 26–97 | Hiragana (gojūon, incl. small kana and dakuten) |
| 98–162 | Katakana ⚠ (index 98 = **ア**) |
| 163–716 | Kanji, by on-reading, ⚠ kun where on is unused (§8.2) |

Only five Latin letters exist in the full-width banks, which is why English
goes through `FONT86.G`.

Because the sort is shared, glyph bitmaps can be diffed between banks to carry
character-table entries across automatically.

---

## 11. Open questions

1. **Displaced kanji on status/equipment screens** (§9.4). `FONT86.G` is
   global; nothing tested so far exercises those screens. Now compounded — the
   high-bit rebuild displaces the katakana range as well. Unverified risk.
2. **Portrait ID → character mapping.** `$00` = Rokudou confirmed. 27 IDs
   remain; `$0001`/`$0201`/`$0202`/`$0203` are probably expression or pose
   variants of the same four party members rather than separate characters.
3. **`$80058` → `$0141A0`** (§5.4). A main-CPU parameter the dialogue loop
   copies before drawing. Purpose unidentified; candidate for a wrap width.
4. **The `$34(A0)` text-offset source** (§7.3). Would allow lengthening strings
   outright rather than substituting word-for-word.
5. **Which bank pairs with `BTL_*.D`.** `BMSG01.K` has 160 glyphs and
   `BTL_10.D` uses 146 distinct codes — a tight fit, though `BTL_10.D`'s max
   code of 713 argues against direct indexing.
6. **`WARNING.MSG`** (65,024 B), **`TMSG01.K` / `XMSG01.K`**, **`O_ASCI.G`** —
   unexamined.
7. **The `SRUN_M.PRG` `MULU #28` sites** (§2) — glyph indexing or unrelated
   record stride?
8. ~~Can `$0D0A` be moved within a block?~~ ⚠ **Moot.** The dialogue renderer
   discards `$0D0A` entirely (§5.4); line breaks are the main CPU's cursor.
   Reflow was never the variable. Word-for-word substitution is the model, and
   it works.
9. ~~`$63C8` / `$63F8` uncatalogued.~~ ⚠ **Answered** (§5.5).
10. ~~The headerless list entry at `0x34F2`.~~ ⚠ **Answered** (§9.6).

---

## 12. Toolchain

See `README.md` for usage. Summary:

| File | Purpose |
|---|---|
| `srblocks.py` | Block-level extractor. `blocks` / `sheet` / `counts` / `verify`. `--en` decodes high-bit English. |
| `hwpatch.py` | Word-for-word English, **plain ASCII** — menus only |
| `hipatch.py` | Word-for-word English, **high-bit** — works everywhere |
| `tailpatch.py` | Original glyphs then ASCII mid-line, for probes |
| `blockpatch.py` | Whole-block rewrite with movable `$0D0A`. Kept for menus; moot for dialogue (§11 item 8) |
| `binpatch.py` | Splice a file into a disc image; recomputes EDC/ECC |
| `mkfont86.py` | Rebuild `FONT86.G` with Latin punctuation |
| `hifont.py` | Mirror `$20`–`$7E` → `$A0`–`$FE` for the high-bit encoding |
| `preview.py` | Render patched blocks exactly as the renderer will |
| `m68kdis.py` | 68k disassembler wrapper (capstone) |
| `audit_table.py`, `verify_glyphs.py`, `priority.py` | Character-table verification |
| `atlasx.py`, `collate.py`, `hwmap.py`, `mkhwmap.py` | Support modules |
| `kanji1_table_v2.py` | Corrected `KANJI1.K` table with occurrence counts |

---

## 13. Legal note

The extracted script is copyrighted material belonging to the rights holders.
Keep dumps private and distribute any release as a **patch**, never as game
files or extracted script data.
