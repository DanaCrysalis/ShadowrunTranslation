"""FONT86.G precomposed voiced/semi-voiced katakana slots.

Recovered by bitmap-diffing FONT86.G against its own JIS X 0201 base kana
(mkhwmap.py), not guessed. Two clean arithmetic rules:

    voiced       = base + 0x30     (0xB6..0xC4 -> 0xE6..0xF4,
                                    0xCA..0xCE -> 0xFA..0xFE)
    semi-voiced  = base + 0xD0     (0xCA..0xCE -> 0x9A..0x9E)
    0xFF         = ヴ              (ウ 0xB3 plus dakuten)

Cross-checks that make this near-certain rather than merely plausible:
  * 0xF5 is one of only four EMPTY slots in the whole file, and it sits at
    exactly ナ+0x30 -- the first base kana after ト that has no voiced form.
  * 0x9E decodes ポケットセクレタリー at 0x3502, which is on screen in the
    ITEM menu.
  * 0xEC decodes メッセージ at 0xD57C and エンジェルクリニック at 0x34F2.
  * 0xFA decodes シルバームーン at 0x3420.

0xE0-0xE5, 0xF6-0xF9 and 0x00-0x1F / 0x7F-0x99 / 0x9F / 0xA0 hold the
status/equipment kanji described in findings §3.2 and are left unmapped.
"""

PRECOMPOSED = {}

# voiced: base + 0x30
for _b, _v in zip(range(0xB6, 0xC5), "\u30ac\u30ae\u30b0\u30b2\u30b4"
                                     "\u30b6\u30b8\u30ba\u30bc\u30be"
                                     "\u30c0\u30c2\u30c5\u30c7\u30c9"):
    PRECOMPOSED[_b + 0x30] = _v                     # ガギグゲゴザジズゼゾダヂヅデド

for _b, _v in zip(range(0xCA, 0xCF), "\u30d0\u30d3\u30d6\u30d9\u30dc"):
    PRECOMPOSED[_b + 0x30] = _v                     # バビブベボ

# semi-voiced: base + 0xD0
for _b, _v in zip(range(0xCA, 0xCF), "\u30d1\u30d4\u30d7\u30da\u30dd"):
    PRECOMPOSED[(_b + 0xD0) & 0xFF] = _v            # パピプペポ

PRECOMPOSED[0xFF] = "\u30f4"                        # ヴ

del _b, _v
