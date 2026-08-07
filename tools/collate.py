"""Gojuon collation: base kana first, then small/large, then dakuten."""
BASE = {}
for a, b in zip("がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ",
                "かきくけこさしすせそたちつてとはひふへほはひふへほ"):
    BASE[a] = b
for a, b in zip("ぁぃぅぇぉっゃゅょゎ", "あいうえおつやゆよわ"):
    BASE[a] = b
VOICED = set("がぎぐげござじずぜぞだぢづでどばびぶべぼ")
SEMI = set("ぱぴぷぺぽ")
SMALL = set("ぁぃぅぇぉっゃゅょゎ")

def key(s):
    base = ''.join(BASE.get(c, c) for c in s)
    small = tuple(1 if c in SMALL else 0 for c in s)
    mark = tuple(2 if c in SEMI else 1 if c in VOICED else 0 for c in s)
    return (base, small, mark)
