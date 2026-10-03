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
# examples-eng release = full JMdict + example sentences (Tatoeba, CC-BY)
JMDICT_PATH = "cache/jmdict-examples-eng-3.6.2.json"
OUT_PATH = "cache/ja-ar.json"

MAX_SENSES = 4
MAX_EXAMPLES_PER_SENSE = 1
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


def render_example(ex: dict) -> str:
    sentences = ex.get("sentences", [])
    jpn = next((t.get("text", "") for t in sentences if t.get("lang") == "jpn"), "")
    eng = next((t.get("text", "") for t in sentences if t.get("lang") == "eng"), "")
    if not jpn and not eng:
        return ""
    line = "مثال: " + cut(jpn) if jpn else ""
    if eng:
        line += ("\n" if line else "") + "→ " + cut(eng)
    return line


def cut(text: str, limit: int = MAX_SENT_LEN) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    # cut at a word/sentence boundary, never mid-word
    clipped = text[:limit]
    for sep in ("。", ". ", "! ", "? ", " ", ""):
        idx = clipped.rfind(sep)
        if idx >= limit * 0.5:
            return clipped[: idx + (1 if sep in ("。",) else 0)].rstrip() + "…"
    return clipped.rstrip() + "…"


def render_sense(sense: dict, en_map: dict):
    """One JMdict sense -> (has_arabic, display string)."""
    glosses = [g["text"] for g in sense.get("gloss", []) if g.get("lang") == "eng" and g.get("text")]
    if not glosses:
        return False, None
    ar = None
    matched_gloss = None
    for g in glosses[:4]:
        ar = lookup_en_ar(en_map, g)
        if ar:
            matched_gloss = g
            break
    if ar:
        line = f"{ar}  [{cut(matched_gloss, 100)}]"
    else:
        # no Arabic bridge for this sense: keep the English definition,
        # clearly bracketed so it reads as the explanation line
        line = f"[{' ; '.join(cut(g, 100) for g in glosses[:2])}]"
    extras = []
    infos = [cut(i, 120) for i in sense.get("info", []) if i]
    if infos:
        extras.append("； ".join(infos[:2]))
    for ex in (sense.get("examples") or [])[:MAX_EXAMPLES_PER_SENSE]:
        r = render_example(ex)
        if r:
            extras.append(r)
    text = line + ("\n" + "\n".join(extras) if extras else "")
    return ar is not None, text


def main() -> int:
    en_map = json.load(open(EN_AR_PATH, encoding="utf-8"))
    jmd = json.load(open(JMDICT_PATH, encoding="utf-8"))["words"]

    out = {}
    translated = 0
    senses_with_examples = 0
    english_only_senses = 0

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

        senses = e.get("sense", [])
        # Render every sense once, then attach per headword using JMdict's
        # appliesToKanji/appliesToKana so heads don't inherit each other's
        # senses (e.g. 猫 vs 猫車 wheelbarrow in the same entry).
        rendered = []
        entry_has_arabic = False
        for s in senses:
            ar_flag, text = render_sense(s, en_map)
            rendered.append((s, ar_flag, text))
            if ar_flag and text:
                entry_has_arabic = True
        if not entry_has_arabic:
            continue

        for h in heads:
            is_kanji = h in kanji
            sense_strings = []
            seen = set()
            for s, ar_flag, text in rendered:
                if not text or text in seen:
                    continue
                # Sense scope: "*" = all heads; otherwise only listed heads.
                k_scope = s["appliesToKanji"]
                n_scope = s["appliesToKana"]
                applies = "*" in (k_scope if is_kanji else n_scope) or h in (k_scope if is_kanji else n_scope)
                if not applies:
                    continue
                seen.add(text)
                sense_strings.append(text)
                if s.get("examples"):
                    senses_with_examples += 1
                if not ar_flag:
                    english_only_senses += 1
                if len(sense_strings) >= MAX_SENSES:
                    break
            if sense_strings:
                out.setdefault(h, " / ".join(sense_strings))
                translated += 1

    # direct kaikki ja->ar translations, if extract_ja_ar_direct.py output exists
    try:
        direct = json.load(open("cache/ja-ar-direct.json", encoding="utf-8"))
        for k, v in direct.items():
            out[k] = v + " / " + out[k] if k in out else v
        print(f"merged {len(direct)} direct ja-ar entries")
    except FileNotFoundError:
        pass

    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(
        f"OK: {len(out)} ja headwords -> {OUT_PATH} "
        f"({translated} arabic-gated entries, {senses_with_examples} senses with examples, "
        f"{english_only_senses} english-explanation senses kept)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
