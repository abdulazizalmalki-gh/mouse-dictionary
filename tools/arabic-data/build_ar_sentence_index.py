#!/usr/bin/env python3
"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Build an Arabic example-sentence index from Tatoeba ara_sentences: for each
Arabic word form (tashkeel-stripped), keep the shortest natural Arabic
sentence containing it. The pack builders attach these as 'مثال:' lines so
tooltips read fully in Arabic without any machine translation.

Matching dictionary headwords against sentence tokens tolerates the common
clitics (ال، وال، فال، بال، لل، وللم، بـ، لـ، و) and the ة/ه spelling variant.

Input: cache/ara_sentences.tsv.bz2   Output: cache/ar_sentence_index.json
Source: Tatoeba https://tatoeba.org (CC BY 2.0 FR; raw download preserves
sentence ids; see DATA_LICENSE.txt).
"""

import bz2
import json
import re

MAX_SENT_LEN = 180
MIN_SENT_LEN = 15
TASHKEEL = re.compile(r"[\u064B-\u0652\u0670\u0640]")
CLITICS = ("وال", "فال", "بال", "ولل", "لل", "ال", "ب", "ل", "و")
NONWORD = re.compile(r"[^\u0600-\u06EF]+")


def strip_diac(text):
    return TASHKEEL.sub("", text)


def variants(token):
    """Headword-form guesses for one sentence token."""
    v = {token}
    for p in CLITICS:
        if token.startswith(p) and len(token) - len(p) >= 2:
            v.add(token[len(p):])
    if token.endswith("ة") and len(token) > 3:
        v.add(token[:-1])
        v.add(token[:-1] + "ه")
    return v


def main():
    index = {}
    with bz2.open("cache/ara_sentences.tsv.bz2", "rt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 3:
                continue
            sent = strip_diac(p[2].strip())
            if not (MIN_SENT_LEN <= len(sent) <= MAX_SENT_LEN):
                continue
            for token in NONWORD.split(sent):
                if len(token) < 2:
                    continue
                for var in variants(token):
                    if len(var) < 2:
                        continue
                    cur = index.get(var)
                    if cur is None or len(sent) < len(cur):
                        index[var] = sent
    json.dump(index, open("cache/ar_sentence_index.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"OK: {len(index)} arabic word forms with example sentences")


if __name__ == "__main__":
    main()
