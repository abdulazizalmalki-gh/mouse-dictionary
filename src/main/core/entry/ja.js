/**
 * Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)
 * Copyright 2018-present wtetsu
 * Licensed under MIT
 */

import UniqList from "uniqlist";
import rule from "../rule";

const RE_ALPHABETS_NUMBERS = /[A-Za-z0-9]/g;
const FULLWIDTH_OFFSET = 0xfee0;

// Halfwidth katakana (U+FF61-FF9F, common in manga/UI text) is normalized to
// its fullwidth form so ﾃﾚﾋﾞ looks up the same headword as テレビ.
// NFKC also folds the semi-voiced/voiced combining sequences (ｶ+ﾞ -> ガ).
const RE_HALFWIDTH_KATAKANA = /[\uFF61-\uFF9F]/;

// A lookup candidate must not cut a katakana run in the middle: ノー from
// ノーベル(...) otherwise hits the unrelated JMdict word ノー ("no") and
// shows a confidently wrong translation when the real compound is missing.
// Hiragana/kanji cuts stay allowed (okurigana: 動いた -> 動く, compounds).
const isKatakana = (code) =>
  (code >= 0x30a1 && code <= 0x30ff) || code === 0x30fc || (code >= 0xff66 && code <= 0xff9d);

const cutsKatakanaRun = (str, len) =>
  len < str.length && isKatakana(str.charCodeAt(len - 1)) && isKatakana(str.charCodeAt(len));

const createLookupWordsJa = (sourceStr) => {
  const str = sourceStr
    .substring(0, 40)
    .replaceAll("\u200c", "") // ZERO WIDTH NON-JOINER
    .replace(RE_ALPHABETS_NUMBERS, (s) => String.fromCharCode(s.charCodeAt(0) + FULLWIDTH_OFFSET));

  const result = new UniqList();

  result.push(sourceStr); // Add the original word

  if (RE_HALFWIDTH_KATAKANA.test(str)) {
    const normalized = str.normalize("NFKC");
    if (normalized !== str) {
      result.push(normalized);
      for (let i = normalized.length; i >= 1; i--) {
        if (cutsKatakanaRun(normalized, i)) {
          continue;
        }
        result.push(normalized.substring(0, i));
      }
    }
  }

  for (let i = str.length; i >= 1; i--) {
    if (cutsKatakanaRun(str, i)) {
      continue;
    }
    const part = str.substring(0, i);
    result.push(part);

    if (i >= 2) {
      const deinedWords = rule.doJa(part);
      result.merge(deinedWords);
    }
  }
  return result.toArray();
};

export default createLookupWordsJa;
