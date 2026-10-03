#!/usr/bin/env python3
"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Build EN->AR dictionary data from kaikki.org (Wiktextract) English-edition
raw JSONL. For each English headword, collect Arabic translations
(translations[].code == "ar"), plus Arabic-sense glosses when no formal
translation is given.

Output: JSON object {headword: "description"} compatible with the
Eijiro-style description format used by data/dict/*.json5 (" / "-separated
senses).

Data source: kaikki.org / Wiktextract, CC BY-SA 4.0 (derived from
en.wiktionary.org). See tools/arabic-data/LICENSE-DATA.txt.
"""

import gzip
import json
import re
import sys
from collections import OrderedDict

AR_CODE = "ar"
MAX_SENSES = 6          # senses per headword
MAX_HEADS = 2           # translation words per sense (strip tags, keep first 2)
MIN_WORDS = 4000        # sanity floor; fail if extraction yields fewer

RE_TAG = re.compile(r"<[^>]+>")
RE_WS = re.compile(r"\s+")


def clean(text: str) -> str:
    if not text:
        return ""
    text = RE_TAG.sub("", text)
    return RE_WS.sub(" ", text).strip()


def sense_text(sense: dict, translations: list) -> str:
    """One sense -> one display string: Arabic words (+ pos/gloss clue)."""
    parts = []
    for t in translations[:MAX_HEADS]:
        w = clean(t.get("word", ""))
        if not w:
            continue
        tags = " ".join(t.get("tags", []) or [])
        # romanization hint is useless for Arabic script; skip 'romanization'
        parts.append(w)
    if not parts:
        return ""
    gloss = clean(sense.get("glosses", [""])[0]) if sense.get("glosses") else ""
    pos = sense.get("pos", "")
    clue = ""
    if pos and pos not in ("unknown",):
        clue = pos
    if gloss:
        # keep gloss short; it disambiguates homographs
        clue = f"({clue}: {gloss[:80]})" if clue else f"({gloss[:80]})"
    joined = ", ".join(parts)
    return f"{joined} {clue}".strip() if clue else joined


def extract(path: str) -> "OrderedDict[str,str]":
    out = OrderedDict()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            word = clean(d.get("word", ""))
            if not word or len(word) > 40:
                continue
            # skip pure inflection-only pages
            if d.get("sense_index") is not None:
                pass  # fine, translations may still exist
            senses = d.get("senses", [])
            sense_strings = []
            seen_sense = set()
            # Raw kaikki format: translations may sit on each sense AND/OR on
            # the page itself (sense-disambiguated vs page-level lists).
            for s in senses:
                trs = [t for t in s.get("translations", []) if t.get("code") == AR_CODE]
                if not trs:
                    continue
                st = sense_text(s, trs)
                if st and st not in seen_sense:
                    seen_sense.add(st)
                    sense_strings.append(st)
                if len(sense_strings) >= MAX_SENSES:
                    break
            if not sense_strings:
                page_trs = [t for t in d.get("translations", []) if t.get("code") == AR_CODE]
                if page_trs:
                    words_ = []
                    for t in page_trs[:MAX_SENSES]:
                        w = clean(t.get("word", ""))
                        if not w or w in words_:
                            continue
                        sense = clean(t.get("sense", ""))
                        words_.append(f"{w} ({sense[:60]})" if sense else w)
                    sense_strings = words_
            if not sense_strings:
                continue
            key = word.lower() if word.lower() not in out else word
            if key in out:
                # merge duplicates from homograph pages
                existing = out[key]
                merged = existing + " / " + " / ".join(s for s in sense_strings if s not in existing)
                out[key] = merged
            else:
                out[key] = " / ".join(sense_strings)
    return out


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    src, dst = sys.argv[1], sys.argv[2]
    data = extract(src)
    if len(data) < MIN_WORDS:
        print(f"ABORT: only {len(data)} entries extracted (floor {MIN_WORDS})", file=sys.stderr)
        return 2
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0, sort_keys=True)
    print(f"OK: {len(data)} en-ar entries -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
