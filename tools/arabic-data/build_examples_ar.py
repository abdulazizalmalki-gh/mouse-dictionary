#!/usr/bin/env python3
"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Build a Japanese->Arabic example-sentence map from Tatoeba exports so the
JA-AR pack shows example translations in Arabic, not English:

    { japanese_sentence_text: arabic_sentence_text }

Edges: direct jpn<->ara links, plus jpn<->eng<->ara pivots (the direct links
alone give ~1.2k pairs; the pivot raises it to ~15k).

Inputs (cache/): jpn_sentences.tsv.bz2, ara_sentences.tsv.bz2,
eng_sentences.tsv.bz2, links.csv   (all from https://downloads.tatoeba.org)
Output (cache/): examples_ar_by_jpn.json

Tatoeba data: https://tatoeba.org, CC BY 2.0 FR; sentence ids are preserved
in the source data (see DATA_LICENSE.txt).
"""

import bz2
import json
import re
import sys
from collections import defaultdict

CACHE = "cache"
MAX_JPN_LEN = 160
MAX_ARA_LEN = 220
TASHKEEL = re.compile(r"[\u064B-\u0652\u0670\u0640]")


def load_lang(code):
    m = {}
    with bz2.open(f"{CACHE}/{code}_sentences.tsv.bz2", "rt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                m[p[0]] = p[2]
    return m


def first_sentence(text):
    for sep in (". ", "！ ", "؟", "!", "?", "。"):
        idx = text.find(sep)
        if 10 < idx < MAX_ARA_LEN:
            return text[: idx + 1].strip()
    return text[:MAX_ARA_LEN].rstrip()


def main():
    jpn = load_lang("jpn")
    ara = load_lang("ara")
    eng = load_lang("eng")

    adj = defaultdict(list)
    with open(f"{CACHE}/links.csv", encoding="utf-8") as f:
        for line in f:
            a, b = line.rstrip("\n").split("\t")
            adj[a].append(b)
            adj[b].append(a)

    out = {}
    direct = 0
    pivots = 0
    for jid, jtext in jpn.items():
        if not (2 <= len(jtext) <= MAX_JPN_LEN):
            continue
        cands = [x for x in adj.get(jid, ()) if x in ara]
        if cands:
            direct += 1
        else:
            cands = [
                x
                for e in adj.get(jid, ())
                if e in eng
                for x in adj.get(e, ())
                if x in ara
            ]
            if cands:
                pivots += 1
        if not cands:
            continue
        cands.sort(key=lambda x: len(ara[x]))
        atext = ara[cands[0]].strip()
        if len(atext) > MAX_ARA_LEN:
            atext = first_sentence(atext)
        if not atext or jtext in out:
            continue
        out[jtext] = atext

    print(f"OK: {len(out)} jpn->ara example pairs ({direct} direct, {pivots} via english pivot)")
    json.dump(out, open(f"{CACHE}/examples_ar_by_jpn.json", "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
