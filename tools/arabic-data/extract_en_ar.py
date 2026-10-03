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
AR_CHAR = re.compile(r"[\u0600-\u06FF]")
MAX_SENSES = 6          # senses per headword
MAX_HEADS = 2           # translation words per sense (strip tags, keep first 2)
MIN_WORDS = 4000        # sanity floor; fail if extraction yields fewer

RE_TAG = re.compile(r"<[^>]+>")
RE_WS = re.compile(r"\s+")
RE_LATIN = re.compile(r"[A-Za-z]")



def clean(text: str) -> str:
    if not text:
        return ""
    text = RE_TAG.sub("", text)
    text = RE_WS.sub(" ", text).strip()
    return text


def scrub_arabic_token(text: str) -> str:
    """Keep Arabic-script characters and punctuation only; strip Latin/CJK
    leftovers (Wiktionary cross-script noise, refs, template ids)."""
    text = re.sub(r"[A-Za-z]{2,}", "", text)  # latin words/fragments
    text = re.sub(r"[\u3000-\u30ff\u3400-\u9fff\uff00-\uffef]", "", text)  # CJK
    text = re.sub(r"[()\[\]{}<>\"'`|_*#]", "", text)  # bracket noise
    text = re.sub(r"\s+", " ", text).strip(" -,؛.")
    return text


def sense_text(sense: dict, translations: list) -> str:
    """One sense -> pure Arabic word list. English qualifiers (glosses, POS
    labels, tags) are deliberately NOT rendered — the pack reads in Arabic.
    Stray Latin inside a translation token is a Wiktionary typo: scrub it and
    re-dedupe so the clean form survives instead."""
    parts = []
    for t in translations[:MAX_HEADS * 2]:  # overfetch: some tokens drop out
        w = scrub_arabic_token(clean(t.get("word", "")))
        if not w or not AR_CHAR.search(w) or w in parts:
            continue
        parts.append(w)
        if len(parts) >= MAX_HEADS:
            break
    return ", ".join(parts)


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
                        if not w or not AR_CHAR.search(w) or w in words_:
                            continue
                        words_.append(w)
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
    # Arabic-first enrichment: definitions (arwiktionary) and example
    # sentences (Tatoeba) so the pack reads fully in Arabic.
    import ar_enrich

    defs, sentences, _ = ar_enrich.load_layers()
    enriched = {}
    dropped = 0
    for word, desc in data.items():
        senses = []
        example = None
        for s in desc.split(" / "):
            first, ex = ar_enrich.annotate(s, defs, sentences)
            # hard Arabic-only gate: no Latin may reach the pack
            if RE_LATIN.search(first):
                dropped += 1
                continue
            senses.append(first)
            if ex and example is None:
                example = ex
        if not senses:
            continue
        out = " / ".join(senses)
        if example:
            out += "\n" + example
        enriched[word] = ar_enrich.scrub(out)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=0, sort_keys=True)
    print(f"OK: {len(enriched)} en-ar entries ({dropped} latin senses dropped) -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
