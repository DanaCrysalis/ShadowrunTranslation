# Shadowrun (Sega CD, JP) — translation toolkit

Tools and tables for a Japanese→English translation patch.

**Read `FINDINGS.md` first.** It is the format spec. The one thing to know
before touching anything: dialogue text must use the **high-bit encoding**
(`ASCII | $80` per byte), because the main-CPU interpreter classifies a word as
text by its sign bit. Plain ASCII works in menus and silently fails in
dialogue. See `FINDINGS.md` §5.5 and §9.2.

---

## Requirements

```
python3, Pillow
pip install capstone     # only for m68kdis.py
pip install pykakasi     # only for audit_table.py / priority.py
```

## Game files you must supply

Not included — extract them from your own disc.

```
ADV_01.D        65,536 B   scenario 1 script
FONT86.G         4,096 B   half-width font
KANJI1.K        32,768 B   full-width bank for ADV_01
SRUN_S.PRG      16,384 B   sub-CPU program        (reference only)
SRUN_X.P        48,384 B   main-CPU interpreter   (reference only)
disc.bin                   the disc image
```

`kanji1_atlas.png` is included and is a lossless render of `KANJI1.K`, so most
tools work without the bank itself.

---

## Build a patch

```bash
# 1. character table -> TSV (index, count, char)
python3 kanji1_table_v2.py kanji1_table.tsv

# 2. translation worksheet, keyed by block
python3 srblocks.py sheet ADV_01.D kanji1_table.tsv adv01_blocks.tsv

# 3. fonts: punctuation first, THEN mirror to the high range
python3 mkfont86.py FONT86.G FONT86_en.G          # or --minimal
python3 hifont.py   FONT86_en.G FONT86_hi.G

# 4. write English
python3 hipatch.py ADV_01.D ADV_01_en.D script.tsv     # dialogue + menus
python3 hwpatch.py ADV_01.D ADV_01_en.D ui.tsv         # menus only, plain ASCII

# 5. preview before flashing (matches hardware glyph-for-glyph)
FONT86=FONT86_hi.G python3 preview.py ADV_01_en.D preview.png 0x3848 0x38F4

# 6. splice into the disc. Second argument is always the STOCK file,
#    and the image must be clean -- binpatch searches for stock bytes.
python3 binpatch.py disc.bin      ADV_01.D  ADV_01_en.D   disc_a.bin
python3 binpatch.py disc_a.bin    FONT86.G  FONT86_hi.G   disc_final.bin
```

`binpatch.py` refuses to write unless it can reproduce the EDC/ECC of sectors
it is *not* modifying, so a layout mismatch fails loudly rather than producing
a subtly corrupt image. `--no-ecc` overrides (fine in emulators, risky on
hardware).

## Check your work

```bash
python3 srblocks.py verify ADV_01_en.D     # must report 0 unaccounted words
python3 srblocks.py blocks ADV_01_en.D kanji1_table.tsv --en | less
```

`--en` decodes `$A0`–`$FE` as high-bit English instead of katakana. It is a
mode, not a guess — the byte values are identical and only context
distinguishes them. Use it on patched files, omit it on stock ones.

---

## Patch file formats

`hipatch.py` and `tailpatch.py` — `offset<TAB>keep<TAB>text`

```
0x003848	0	Same old Silver Moon.
0x0038F4	4	Mid Eng
```

`offset` is the start of a **line**. `keep` is how many original cells to leave
untouched at its head, so text can go in the middle. Text is padded to an even
length; it must not exceed `(cells - keep) * 2` characters.

`hwpatch.py` — `offset<TAB>text[<TAB>cells]`, plain ASCII, menus only.

`blockpatch.py` — `@<hex offset>` then one line of text per output line. Holds
the block's total word count constant but lets `$0D0A` move. Useful for menus;
moot for dialogue.

---

## Character-table verification

```bash
python3 srblocks.py counts ADV_01.D counts.tsv
python3 verify_glyphs.py glyph_verify.tsv      # slow, a few minutes
python3 audit_table.py counts.tsv
python3 priority.py > handcheck.txt
```

`handcheck.txt` is the short list actually worth eyeballing against
`kanji1_atlas.png` — 26 indices, not 392. `FINDINGS.md` §8.2 explains why
frequency is the wrong filter and what replaces it.

---

## Disassembly

```bash
python3 m68kdis.py SRUN_S.PRG 10000 153c:38     # sub CPU, load base $00010000
python3 mdis.py    SRUN_X.P   0     1342:20     # main CPU, base $0
```

Addresses worth knowing are in `srun_s_loops.md` and `FINDINGS.md` §5.

---

## Next steps

1. **Translate.** The format is settled; `adv01_blocks.tsv` has an empty
   `english` column, with speaker ID and per-line budget as context.
2. **Check the status/equipment screens** against the rebuilt font. Both
   rebuilds displace glyphs and nothing has exercised those screens yet — the
   only unverified risk left (`FINDINGS.md` §11 item 1).
3. **Write a bank-differ.** All banks share sort order, so matching bitmaps
   between `KANJI1.K` and `KANJI2.K` carries most of the 717 known characters
   across, leaving only new glyphs to identify by hand.
4. **Extend to `ADV_02`–`ADV_11` and `BTL_*`.**

## Legal

The extracted script is copyrighted. Keep dumps private and distribute any
release as a **patch**, never as game files or script data.
