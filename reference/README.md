# Reference

`kanji1_atlas.png`  lossless 2x render of KANJI1.K. `atlasx.py` reads the
                    original bitmaps back out of it, so most tools work
                    without the bank file itself.
`srtext.py`         the ORIGINAL extractor. Superseded by srblocks.py: its
                    parse() treats every sub-$8000 word as a terminator, which
                    splits blocks at every control run. Kept for its atlas and
                    font-rendering commands.
`adv01_script.tsv`  output of that old extractor -- 963 fragments where the
                    real structure is 968 blocks. Kept for comparison only.
