#!/usr/bin/env python3
"""
Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)

Build the Arabic-definition layer (AR->AR) from the ar.wiktionary.org dump so
the Arabic packs can explain their Arabic equivalents IN Arabic instead of
leaving English glosses behind.

Page layouts on arwiktionary:

  Modern:  == {{اللغة|عربية}} ==   <- level-2 language header
           === اسم ===             <- level-3 part-of-speech header
           # [[حَيَوَان|حَيْوَان]] مستأنس من عائلة ال[[سَنُّورِيّات]]، ...

  Older:   (no language headers) ... just === المعاني === and # lines.

Definitions are cleaned hard: entity-escaped <ref> citations (which nest
{{استشهاد بويكي بيانات|qid=…|المسار=https://…}} templates), raw templates,
category links and wikidata ids are all DELETED. Template *expansion* is used
only when matching section headers ({{اللغة|عربية}} -> عربية). Any definition
still containing a Latin letter after cleaning is rejected outright, so the
layer can never leak English into an Arabic pack.

Output: cache/ar_defs.json  {stripped_arabic_word: "تعريف1؛ تعريف2"}
        cache/ar_quotes.json {stripped_arabic_word: first usage quote}
Source: arwiktionary dump, CC BY-SA 4.0 (Wikimedia).
"""

import bz2
import json
import re
import sys

MAX_DEFS = 2
MAX_DEF_LEN = 150
TASHKEEL = re.compile(r"[\u064B-\u0652\u0670\u0640]")
AR = re.compile(r"[\u0600-\u06FF]")
LATIN = re.compile(r"[A-Za-z]")

LINK = re.compile(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]+)\]\]")
URL = re.compile(r"\[(?:[^\[\]]*\s)?([^\[\]]+)\]")
TPL_ANY = re.compile(r"\{\{[^{}]*\}\}")
TPL_INNER = re.compile(r"\{\{[^|{}]*\|([^{}]*)\}\}|\{\{([^{}|]*)\}\}")
HDR = re.compile(r"^\s*(={2,6})\s*(.+?)\s*\1\s*$")

# A level-2 header naming Arabic marks the block we want; any other named
# language closes it.
LANG_AR = re.compile(r"عرب")
LANG_OTHER = re.compile(
    r"إنجليز|فرنس|ألماني|أسباني|إيطالي|برتغالي|روس|تركي|فار|كرد|عبري|لاتين|هندي|صيني|كوري|الياباني|"
    r"english|french|german|latin", re.I)

# POS / meaning headers that introduce definition lists
POS_OK = re.compile(
    r"^(?:المعاني|معاني|معانٍ|معنى|المعنى|تعريف|التعريف|اسم|أسماء|اسم علم|فعل|أفعال|"
    r"صفة|صفه|ظرف|حرف|أداة|أدوات|مصدر|كلمة|الكلمة|اسم جمع|صيغة|تصريف|اسم فعل|حروف)$")
POS_STOP = re.compile(
    r"^(?:المراجع|النطق|المنطق|الاشتقاق|الكلمات ذات صلة|من الجذر نفسه|التصريفات|"
    r"ترجمات|الترجمات|ملاحظة|ملاحظات|انظر أيضاً|فهرس|قوائم|جذور|مشتقات)$")


def decode_entities(text):
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#34;", '"'),
                 ("&#034;", '"'), ("&apos;", "'"), ("&#39;", "'"), ("&#039;", "'"),
                 ("&nbsp;", " "), ("&amp;", "&")):
        text = text.replace(a, b)
    return text


def strip_citations(text):
    # refs may be entity-escaped with nested templates inside; decode first,
    # then remove both self-closing and paired forms
    text = re.sub(r"<ref\b[^>]*/>", "", text)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S)
    # leftovers of partially-stripped citation templates
    text = re.sub(r"(?:qid|الصفحة|المجلد|المسار)\s*=\s*[^\s|؛،]+", "", text)
    return text


def definition_text(text):
    """Clean for DEFINITION content: remove templates and tags entirely.
    Returns '' when Latin survives (reject the definition)."""
    prev = None
    while prev != text:
        prev = text
        text = TPL_ANY.sub("", text)
    text = re.sub(r"<[^>]*>", "", text)
    # category/special links (leading colon) are dropped entirely
    text = re.sub(r"\[\[:[^\]]*\]\]", "", text)
    # normal wiki links keep their visible text: [[حَيَوَان|حَيْوَان]] -> حَيْوَان
    prev = None
    while prev != text:
        prev = text
        text = LINK.sub(r"\1", text)
        text = URL.sub(r"\1", text)
    text = decode_entities(text)
    text = strip_citations(text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"\bQ\d{3,}\b[^\s\u0600-\u06FF]*", "", text)
    text = re.sub(r"[،؛]\s*[،؛]", "؛", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("#:*.| ")
    if LATIN.search(text):
        return ""
    return text


def header_text(text):
    """Clean for HEADER matching: expand {{x|y}} -> y so language names inside
    templates ({{اللغة|عربية}}) match."""
    prev = None
    while prev != text:
        prev = text
        text = TPL_INNER.sub(r"\1", text)
        text = LINK.sub(r"\1", text)
    text = decode_entities(text)
    text = re.sub(r"[=\s]+", " ", text).strip(":* '\" ")
    return text


def strip_diacritics(text):
    return TASHKEEL.sub("", text)


def trim(text, limit=MAX_DEF_LEN):
    text = text.strip("؛،. ")
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("،", "؛", " "):
        idx = cut.rfind(sep)
        if idx > limit * 0.4:
            return cut[:idx].rstrip(" ،؛.") + "…"
    return cut.rstrip(" ،؛.") + "…"


def collect(lines):
    """Return (definitions, first_quote) from the Arabic block of one page."""
    mode = "plain"        # no language header seen: المعاني-style only
    in_block = False      # inside Arabic level-2 block
    in_pos = False        # inside a POS/meaning section
    seen_header = False   # preamble of unmarked pages counts as headword text
    defs = []
    quote = None
    for raw in lines:
        m = HDR.match(raw)
        if m:
            seen_header = True
            depth = len(m.group(1))
            hname = header_text(m.group(2))
            if depth == 2:
                if LANG_AR.search(hname):
                    mode = "langblock"
                    in_block = True
                    in_pos = False
                elif LANG_OTHER.search(hname):
                    in_block = False
                    in_pos = False
                elif POS_STOP.match(hname):
                    in_pos = False
                elif POS_OK.match(hname):
                    in_pos = True
            elif depth >= 3:
                if POS_STOP.match(hname):
                    in_pos = False
                elif POS_OK.match(hname):
                    in_pos = True
            continue
        if raw.startswith("{{توضيح"):
            return [], None
        if mode == "langblock" and not in_block:
            continue
        if not in_pos and not (mode == "plain" and not seen_header):
            continue
        s = raw.strip()
        if not s.startswith("#"):
            continue
        if s.startswith("#:") or s.startswith("#*"):
            if quote is None:
                t = definition_text(s[2:].strip())
                if t and AR.search(t) and 6 <= len(t) <= 140:
                    quote = trim(t, 140)
            continue
        if s[1:2] == ";":
            continue
        t = definition_text(s.lstrip("#").strip())
        if not t or not AR.search(t) or len(t) < 5:
            continue
        t = trim(t)
        if t not in defs:
            defs.append(t)
        if len(defs) >= MAX_DEFS:
            break
    return defs, quote


def process(title, text, defs_out, quotes_out):
    if title.startswith(("تصنيف:", "ملحق:", "قالب:", "فهرس:", "القالب", "الفهرس", "الجذر")):
        return
    defs, quote = collect(text.split("\n"))
    if defs:
        key = strip_diacritics(title)
        defs_out.setdefault(key, "؛ ".join(defs[:MAX_DEFS]))
        if quote:
            quotes_out.setdefault(key, quote)


def main():
    src = "cache/arwikt.xml.bz2"
    dst = "cache/ar_defs.json"
    qdst = "cache/ar_quotes.json"
    out = {}
    quotes = {}
    title = None
    in_text = False
    body = []
    pages = 0

    with bz2.open(src, "rt", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "<title>" in line and "<text" not in line:
                m = re.search(r"<title>(.*?)</title>", line)
                title = m.group(1) if m else None
                continue
            if "<text" in line:
                in_text = True
                body = []
                continue
            if "</text>" in line:
                in_text = False
                if title and AR.search(title) and body:
                    pages += 1
                    process(title, "".join(body), out, quotes)
                    if pages % 100000 == 0:
                        print(f"  ...{pages} pages, {len(out)} defs", file=sys.stderr)
                title = None
                body = []
                continue
            if in_text:
                body.append(line)

    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(quotes, open(qdst, "w", encoding="utf-8"), ensure_ascii=False)
    latin = sum(1 for v in out.values() if LATIN.search(v))
    print(f"OK: {pages} arabic pages -> {len(out)} definitions -> {dst}; "
          f"{len(quotes)} quotes -> {qdst}; latin leaks in defs: {latin}")


if __name__ == "__main__":
    sys.exit(main())
