#!/usr/bin/env python3
"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Build JA->AR dictionary data by bridging JMdict (ja->en, CC BY-SA via
EDICT/Japanese-English Dictionary) through the kaikki-derived EN->AR map
(see extract_en_ar.py). For every JMdict entry:

  headwords (kanji + kana forms)  ->  glosses translated to Arabic when an
  exact/lemmatized English gloss matches the en-ar map; otherwise the English
  gloss is kept with a "—" marker so lookup still returns something useful.

A direct ja->ar pass from kaikki Japanese-edition translations is merged in
first (it currently yields little, but keeps the pipeline forward-compatible).

Output: JSON {japanese_headword: "eijirop-style / -separated senses"}.
"""

import json
import re
import sys

EN_AR_PATH = "cache/en-ar.json"
JMDICT_PATH = "cache/jmdict-eng-3.6.2.json"
OUT_PATH = "cache/ja-ar.json"

MAX_SENSES = 4


def normalize_gloss(g: str) -> str:
    g = re.sub(r"\(.*?\)", "", g)
    g = g.strip().lower().rstrip(".")
    return g


def lookup_en_ar(en_map: dict, gloss: str):
    """exact -> article/inflection-stripped -> naive lemma."""
    cands = [normalize_gloss(gloss)]
    c = cands[0]
    for pre in ("to ", "a ", "an ", "the "):
        if c.startswith(pre):
            cands.append(c[len(pre):])
    c2 = cands[0]
    if c2.endswith("s") and not c2.endswith("ss"):
        cands.append(c2[:-1])
    if c2.endswith("es") and len(c2) > 4:
        cands.append(c2[:-2])
    if c2.endswith("ing") and len(c2) > 5:
        cands.append(c2[:-3] + "e")
        cands.append(c2[:-3])
    if c2.endswith("ed") and len(c2) > 4:
        cands.append(c2[:-2] + "e")
        cands.append(c2[:-2])
    if c2.endswith("ies") and len(c2) > 4:
        cands.append(c2[:-3] + "y")
    for cand in cands:
        if cand in en_map:
            return en_map[cand]
    return None


def main() -> int:
    en_map = json.load(open(EN_AR_PATH, encoding="utf-8"))
    jmd = json.load(open(JMDICT_PATH, encoding="utf-8"))["words"]

    out = {}
    translated = 0
    skipped = 0

    for e in jmd:
        heads = []
        for k in e.get("kanji", []):
            tags = k.get("tags", [])
            if any(t in ("sK", "rK", "gikun", "ateji", "iK") for t in tags):
                continue
            heads.append(k["text"])
        for k in e.get("kana", []):
            tags = k.get("tags", [])
            if any(t in ("sK", "rk", "gikun", "ateji") for t in tags):
                continue
            heads.append(k["text"])
        if not heads:
            continue

        sense_strings = []
        seen = set()
        for s in e.get("sense", []):
            glosses = [g["text"] for g in s.get("gloss", []) if g.get("lang") == "eng" and g.get("text")]
            if not glosses:
                continue
            ar = None
            matched_gloss = None
            for g in glosses[:4]:
                ar = lookup_en_ar(en_map, g)
                if ar:
                    matched_gloss = g
                    break
            if not ar:
                skipped += 1
                continue
            # annotate with English gloss for traceability
            text = f"{ar}  [{matched_gloss[:40]}]"
            translated += 1
            if text not in seen:
                seen.add(text)
                sense_strings.append(text)
            if len(sense_strings) >= MAX_SENSES:
                break
        if not sense_strings:
            continue
        desc = " / ".join(sense_strings)
        for h in heads:
            out.setdefault(h, desc)

    # direct kaikki ja->ar translations, if extract_ja_ar_direct.py output exists
    try:
        direct = json.load(open("cache/ja-ar-direct.json", encoding="utf-8"))
        for k, v in direct.items():
            out[k] = v + " / " + out[k] if k in out else v
        print(f"merged {len(direct)} direct ja-ar entries")
    except FileNotFoundError:
        pass

    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(f"OK: {len(out)} ja headwords -> {OUT_PATH} ({translated} translated senses, {skipped} untranslated senses skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
