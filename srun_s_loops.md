# `SRUN_S.PRG` draw loops — disassembled

Load base `$00010000`. Verified against the file: 16,384 bytes.

## There are exactly three draw loops, and only three dispatcher call sites

```
file 0x1590  ($011590)  BSR.W $01167E     <- loop at $01153C   DIALOGUE
file 0x15E4  ($0115E4)  BSR.W $0112D2     <- loop at $0115A2   menu, $08xxxx mailbox
file 0x165C  ($01165C)  BSR.W $0112D2     <- loop at $0115FE   menu, $0Cxxxx mirror
file 0x179A  ($01179A)  BSR.W $0117AA     <- atlas/debug dump
```

Only the two menu loops write the count mailboxes:

```
$0115CE  MOVE.W D4,$8000C     line count
$0115F0  MOVE.W D5,$8000A     cell count
$011646  MOVE.W D4,$C000C
$011668  MOVE.W D5,$C000A
```

**`$01153C` writes neither.** Dialogue window geometry does not come from the
sub CPU at all. This corrects §6.1, which read the dynamic counting as the
general mechanism — it is menu-only.

## The dialogue loop — `$01153C`

```asm
01155C  MOVEA.L $80036,A3          ; output buffer (NOT $80006)
011552  MOVE.W  $80058,$141A0      ; a parameter from the main CPU
011562  MOVE.W  (A1),D0
011564  LSR.W   #8,D0
011566  CMPI.B  #$23,D0
01156A  BEQ.W   $1158E             ; leading $23xx -> draw nothing
01156E  MOVE.W  (A1)+,D0           ; <-- loop top
011570  MOVE.W  D0,D3
011572  LSR.W   #8,D3
011574  CMPI.B  #$0D,D3
011578  BEQ.B   $1156E             ; high byte $0D -> SKIP, draw nothing,
                                   ;   A3 NOT advanced, next word
01157A  CMPI.B  #$24,D3
01157E  BEQ.W   $1158E             ; rts
011582  CMPI.B  #$23,D3
011586  BEQ.W   $1158E             ; rts
011590  BSR.W   $01167E            ; glyph dispatcher
011594  BRA.B   $1156E
```

Two things fall out.

**No half-width filter exists.** The loop terminates only on high byte `$23`
or `$24`. Every other word goes to the dispatcher. So the sub CPU renders
half-width in dialogue without complaint — which is exactly what the screen
showed once the English was moved off the head of a line.

**`$0D0A` is discarded.** It is consumed and skipped; `A3` does not advance and
no row break is emitted. The sub CPU streams cells linearly into `(A3)`.
Whatever produces visual line breaks in dialogue is upstream, on the main CPU.

## Buffer footprint — identical on both paths, at both dispatchers

Full-width (`$0112D2` tail at `$011366`, `$01167E` tail at `$0116FA`):

```asm
        MOVE.L  D4,$40(A3)         ; right column strip
        MOVE.L  D3,(A3)+           ; left column strip, 16 rows x 4 bytes
        DBRA    D7,...             ;   = 64 bytes
        ...
        ADDA.L  #$40,A3            ; + 64 = 128 bytes per word
```

Half-width (`$0113A6` and `$011728`), called twice per word:

```asm
        MOVE.W  #$F,D7             ; 16 rows
        MOVE.L  D3,(A3)+           ;   x 4 bytes = 64 bytes per GLYPH
        DBRA    D7,...             ; x2 glyphs  = 128 bytes per word
```

**128 bytes per source word either way**, and the same left-then-right byte
layout. §5.3 is confirmed at both dispatchers, not just the one.

## What this leaves

The sub CPU renders the patched dialogue correctly. The truncation is
therefore on the main CPU, which is deciding how much to transfer or display
and changing that decision when half-width words are present. The relevant
code is in `SRUN_X.P` (the `$1FA0` region of §6.1) and possibly the `COM_*.P`
overlays, neither of which has been examined.

Note also `$011552`: the dialogue loop copies `$80058` into a local at
`$0141A0` before drawing. That is a main-CPU-supplied parameter whose purpose
is unidentified, and it is a candidate for the wrap width.
