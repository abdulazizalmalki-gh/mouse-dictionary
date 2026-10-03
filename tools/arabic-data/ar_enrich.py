"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Shared Arabic enrichment layer for the en-ar / ja-ar pack builders. The packs
must read fully in Arabic, so every English string that used to ride along
(Wiktionary gloss qualifiers, JMdict [english] tags, English example
translations) is replaced with Arabic material from open sources:

  cache/ar_defs.json            Arabic word -> Arabic definition
                                (built from arwiktionary by build_ar_defs.py)
  cache/ar_sentence_index.json  Arabic word -> natural Arabic example sentence
                                (built from Tatoeba ara_sentences by
                                build_ar_sentence_index.py)
  cache/examples_ar_by_jpn.json Japanese sentence -> Arabic sentence
                                (built from Tatoeba by build_examples_ar.py)

Lookups ignore tashkeel/tatweel: the pack forms may or may not carry
diacritics, the indexes are stored stripped.
"""

import json
import os
import re

TASHKEEL = re.compile(r"[\u064B-\u0652\u0670\u0640]")
AR_CHAR = re.compile(r"[\u0600-\u06FF]")
SEP = re.compile(r"[,،]")


def strip_diac(text: str) -> str:
    return TASHKEEL.sub("", text)


def scrub(text: str) -> str:
    """Final pack-level cleanup: drop empty definition parentheses and collapse
    dangling separators left after Latin/citation stripping."""
    # () or (؛) or (. :) leftovers
    text = re.sub(r"\(\s*[؛،.:.\s]*\)", "", text)
    # leading/trailing separators inside remaining parens
    text = re.sub(r"\(\s*[؛،.]+\s*", "(", text)
    text = re.sub(r"[؛،.]{2,}", "؛", text)
    # duplicate consecutive senses ('X / X') and empty sense segments
    parts = [p.strip() for p in text.split(" / ") if p.strip(" /؛،.")]
    deduped = []
    for p in parts:
        if p not in deduped:
            deduped.append(p)
    out = " / ".join(deduped)
    return re.sub(r"\n+", "\n", out).strip()


def load_layers(cache_dir="cache"):
    """Return (defs, sentences, jp_examples); missing files yield {}.

    Each lookup function tolerates the missing layer, so a partial cache
    still builds valid (less-annotated) packs."""
    def _read(name):
        p = os.path.join(cache_dir, name)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}

    return _read("ar_defs.json"), _read("ar_sentence_index.json"), _read("examples_ar_by_jpn.json")


def first_ar_word(sense: str) -> str:
    """The leading Arabic token of a sense string like 'كِتَاب, دِفْتَر ...'."""
    head = sense.split(" (")[0]
    for part in SEP.split(head):
        part = part.strip()
        if part and AR_CHAR.search(part):
            return part.split(" ")[0].strip()
    return ""


def annotate(ar_sense: str, defs: dict, sentences: dict):
    """Append the Arabic definition to a bare Arabic word list.
    Returns (text, example_or_None)."""
    key = strip_diac(first_ar_word(ar_sense))
    text = ar_sense
    example = None
    if key and key in defs:
        text = f"{ar_sense} ({defs[key]})"
        if key in sentences:
            example = f"مثال: {sentences[key]}"
    return text, example
