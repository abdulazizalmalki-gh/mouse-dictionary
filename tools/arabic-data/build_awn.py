#!/usr/bin/env python3
"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Arabic WordNet 4.x (AWN) layer: joins AWN (Arabic, CC BY 4.0) to Open
English WordNet on synset offsets (AWN ids are literally the OEWN offset),
producing cache/awn-en-ar.json consumed by the pack builders:

  {english lemma (lowercase): [{ar:[lemmas], def:arabic-def, ex:arabic-example}, ...]}

One list item per synset (sense); the def/example belong to the SAME synset
as the lemmas — by-word definition lookups attach wrong-sense glosses and are
forbidden. This is the missing modern-vocabulary layer: Arabic Wiktionary has
no translation tables for 'arcade'/'incentive'/'barcode'; WordNet coverage
fills them, and its sense order is authoritative.

Sources (download to cache/):
  https://raw.githubusercontent.com/Salah-Sal/arabic-wordnet-v4/main/output/awn4.xml.gz
  https://github.com/globalwordnet/english-wordnet/releases  (english-wordnet-2025.xml.gz)
"""

import gzip
import html
import json
import re
import sys

from build_ar_defs import definition_text

AWN_PATH = "cache/awn4.xml.gz"
OEWN_PATH = "cache/oewn-2025.xml.gz"

LEMMA = re.compile(r'<Lemma writtenForm="([^"]*)" partOfSpeech="([a-z]+)"')
SENSE = re.compile(r'<Sense id="[^"]*" synset="([a-z0-9]+-\d+-[a-z])"')
SYNSET_ID = re.compile(r'<Synset id="[a-z0-9]+-(\d+-[a-z])"')
DEFINITION = re.compile(r"<Definition>(.*?)</Definition>", re.S)
EXAMPLE = re.compile(r"<Example>(.*?)</Example>", re.S)

MAX_SENSES = 4
MAX_LEMMAS = 3
MAX_HEADS = 2


def render_senses(senses, max_heads=MAX_HEADS, max_senses=MAX_SENSES):
    """AWN sense list -> pack display string ('a, b (def) / c, d\\nمثال: ex') or None.

    Shared by extract_en_ar.py (direct AWN fill) and build_ja_ar.py (bridge
    fallback) so both render the synset-attached def/example identically.
    Every line passes the same Arabic-only contract as the rest of the
    pipeline: lemmas without Arabic are dropped, pure-Arabic assumed elsewhere.
    """
    ar_char = re.compile(r"[\u0600-\u06FF]")
    rendered = []
    for s in senses:
        lemmas = [w for w in s["ar"] if ar_char.search(w)][:max_heads]
        if not lemmas:
            continue
        line = ", ".join(lemmas)
        if s["def"]:
            line += f" ({s['def']})"
        rendered.append(line)
        if len(rendered) >= max_senses:
            break
    if not rendered:
        return None
    out = " / ".join(rendered)
    ex = next((s["ex"] for s in senses if s["ex"]), None)
    if ex:
        out += "\nمثال: " + ex
    return out


def bare_id(sid: str) -> str:
    """'awn4-15215063-n' -> '15215063-n' (AWN ids mirror OEWN offsets)."""
    return sid.split("-", 1)[1] if sid.startswith("awn4-") else sid


def parse_awn():
    """offset-pos -> (arabic lemmas by entry order, first definition, first example)."""
    syn_lemmas = {}
    with gzip.open(AWN_PATH, "rt", encoding="utf-8") as f:
        # lexical entries: lemma followed by its senses
        cur_lemma = None
        cur_pos = None
        for line in f:
            m = LEMMA.search(line)
            if m:
                cur_lemma, cur_pos = html.unescape(m.group(1)), m.group(2)
                continue
            m = SENSE.search(line)
            if m and cur_lemma:
                sid = bare_id(m.group(1))
                if not sid.endswith(cur_pos):
                    continue  # pos mismatch guard
                syn_lemmas.setdefault(sid, [])
                if cur_lemma not in syn_lemmas[sid]:
                    syn_lemmas[sid].append(cur_lemma)
    syn_defs = {}
    syn_examples = {}
    with gzip.open(AWN_PATH, "rt", encoding="utf-8") as f:
        cur = None
        for line in f:
            m = SYNSET_ID.search(line)
            if m:
                cur = m.group(1)
                continue
            if cur:
                m = DEFINITION.search(line)
                if m and cur not in syn_defs:
                    syn_defs[cur] = html.unescape(m.group(1))
                    continue
                m = EXAMPLE.search(line)
                if m and cur not in syn_examples:
                    syn_examples[cur] = html.unescape(m.group(1))
        del cur
    return syn_lemmas, syn_defs, syn_examples


def parse_oewn():
    """english lemma (lowercase, also with _ variants) -> set(offset-pos)."""
    en_ssets = {}
    with gzip.open(OEWN_PATH, "rt", encoding="utf-8") as f:
        cur_lemma = None
        for line in f:
            m = LEMMA.search(line)
            if m:
                cur_lemma = html.unescape(m.group(1))
                continue
            m = SENSE.search(line)
            if m and cur_lemma:
                sid = m.group(1)
                if not sid.startswith("oewn-"):
                    continue
                key = cur_lemma.lower()
                en_ssets.setdefault(key, set())
                en_ssets[key].add(sid[5:])
    return en_ssets


def main():
    syn_lemmas, syn_defs, syn_examples = parse_awn()
    en_ssets = parse_oewn()

    en_ar = {}
    for word, ssets in en_ssets.items():
        senses = []
        for sid in sorted(ssets):  # synset order = wordnet sense order
            lemmas = []
            for lemma in syn_lemmas.get(sid, []):
                clean = definition_text(lemma)
                if clean and clean not in lemmas:
                    lemmas.append(clean)
            if not lemmas:
                continue
            d = definition_text(syn_defs.get(sid, ""))
            e = definition_text(syn_examples.get(sid, ""))
            if d and len(d) < 8:
                d = ""
            if d and len(d) > 150:
                d = d[:150].rsplit(" ", 1)[0] + "…"
            if e and not (8 <= len(e) <= 140):
                e = ""
            senses.append({"ar": lemmas[:MAX_LEMMAS], "def": d or "", "ex": e or ""})
            if len(senses) >= MAX_SENSES:
                break
        if senses:
            en_ar[word] = senses

    json.dump(en_ar, open("cache/awn-en-ar.json", "w", encoding="utf-8"),
              ensure_ascii=False, sort_keys=True)
    print(f"OK: {len(en_ar)} en->ar wordnet senses -> cache/awn-en-ar.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
