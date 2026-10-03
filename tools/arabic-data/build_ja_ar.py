#!/usr/bin/env python3
"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Build JA->AR dictionary data by bridging JMdict (ja->en, CC BY-SA via EDRDG)
through the kaikki-derived EN->AR map (extract_en_ar.py). The output is
strictly Arabic: the English pivot glosses appear nowhere; explanations and
examples come from the Arabic layers in ar_enrich:

  ar_defs.json            Arabic gloss -> Arabic definition (arwiktionary)
  ar_sentence_index.json  Arabic word -> Arabic example sentence (Tatoeba)
  examples_ar_by_jpn.json Japanese sentence -> Arabic sentence (Tatoeba,
                          joined to JMdict examples by Tatoeba sentence id)

A sense with no Arabic bridge is kept only as ride-along context when the
entry has at least one bridged sense — and even then rendered Arabic-first:
bridged senses carry the Arabic annotation; unbridged senses are dropped
entirely from the output.

Output: cache/ja-ar.json  {japanese_headword: "Arabic eijiro-style senses"}
"""

import json
import re
import sys

import ar_enrich

EN_AR_PATH = "cache/en-ar.json"
# examples-eng release = full JMdict + example sentences (Tatoeba-sourced)
JMDICT_PATH = "cache/jmdict-examples-eng-3.6.2.json"
OUT_PATH = "cache/ja-ar.json"

MAX_SENSES = 4
MAX_SENT_LEN = 140


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


def cut(text: str, limit: int = MAX_SENT_LEN) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    for sep in ("。", ". ", "! ", "? ", " "):
        idx = clipped.rfind(sep)
        if idx >= limit * 0.5:
            return clipped[: idx + (1 if sep == "。" else 0)].rstrip() + "…"
    return clipped.rstrip() + "…"


def example_ar_line(ex: dict, jp_ar_examples: dict) -> str:
    """A JMdict example -> 'مثال: <japanese>' line; the Arabic translation is
    attached separately after the sense via the jp text map (never English)."""
    jpn = next((t.get("text", "") for t in ex.get("sentences", []) if t.get("lang") == "jpn"), "")
    if not jpn:
        return ""
    return cut(jpn)


def render_sense(sense: dict, en_map: dict, defs: dict, sentences: dict, jp_ar: dict):
    """One JMdict sense -> Arabic display text, or None if no Arabic bridge.

    The en_map values are already Arabic-enriched (definition + مثال line) by
    extract_en_ar.py; only annotate when a line lacks that, never twice.
    """
    glosses = [g["text"] for g in sense.get("gloss", []) if g.get("lang") == "eng" and g.get("text")]
    if not glosses:
        return None
    ar = None
    for g in glosses[:4]:
        ar = lookup_en_ar(en_map, g)
        if ar:
            break
    if ar is None:
        return None
    parts = ar.split("\n")
    sense_line = parts[0]
    example = parts[1] if len(parts) > 1 and parts[1].startswith("مثال:") else None
    if " (" not in sense_line:
        sense_line, ex = ar_enrich.annotate(sense_line, defs, sentences)
        example = example or ex
    text = sense_line
    if not example:
        # try a JMdict example with a known Arabic translation instead;
        # reject if the Arabic translation itself contains latin runs (the
        # pack gate below is zero-tolerance)
        for ex in (sense.get("examples") or [])[:1]:
            jpn = example_ar_line(ex, jp_ar)
            ar_sent = jp_ar.get(jpn)
            if ar_sent and not re.search(r"[A-Za-z]{2,}", ar_sent):
                example = f"مثال: {cut(jpn)} — {cut(ar_sent, 120)}"
                break
    if example:
        text = text + "\n" + example
    return text


def main() -> int:
    en_map = json.load(open(EN_AR_PATH, encoding="utf-8"))
    jmd = json.load(open(JMDICT_PATH, encoding="utf-8"))["words"]
    defs, sentences, jp_ar = ar_enrich.load_layers()

    out = {}
    entries = 0
    with_ar_example = 0
    with_jmdict_example = 0

    for e in jmd:
        kanji = [
            k["text"]
            for k in e.get("kanji", [])
            if not any(t in ("sK", "rK", "gikun", "ateji", "iK") for t in k.get("tags", []))
        ]
        kana = [
            k["text"]
            for k in e.get("kana", [])
            if not any(t in ("sK", "rk", "gikun", "ateji") for t in k.get("tags", []))
        ]
        heads = kanji + kana
        if not heads:
            continue

        # Render only bridged (Arabic) senses; per-headword scoping follows
        # JMdict appliesToKanji/appliesToKana so heads don't inherit senses.
        rendered = []
        for s in e.get("sense", []):
            text = render_sense(s, en_map, defs, sentences, jp_ar)
            if text:
                rendered.append((s, text))
        if not rendered:
            continue

        for h in heads:
            is_kanji = h in kanji
            sense_strings = []
            seen = set()
            for s, text in rendered:
                if text in seen:
                    continue
                k_scope = s["appliesToKanji"]
                n_scope = s["appliesToKana"]
                applies = "*" in (k_scope if is_kanji else n_scope) or h in (k_scope if is_kanji else n_scope)
                if not applies:
                    continue
                seen.add(text)
                sense_strings.append(text)
                if len(sense_strings) >= MAX_SENSES:
                    break
            if not sense_strings:
                continue
            desc = " / ".join(sense_strings)
            desc = ar_enrich.scrub(desc)
            if "مثال:" in desc:
                if " — " in desc:
                    with_jmdict_example += 1
                else:
                    with_ar_example += 1
            out.setdefault(h, desc)
        entries += 1

    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(
        f"OK: {len(out)} ja headwords -> {OUT_PATH} ({entries} arabic-gated entries; "
        f"examples: {with_ar_example} arabic-natural, {with_jmdict_example} from JMdict sentences)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
