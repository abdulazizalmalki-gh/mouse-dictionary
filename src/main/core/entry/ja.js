/**
 * Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)
 * Copyright 2018-present wtetsu
 * Licensed under MIT
 */

import UniqList from "uniqlist";
import rule from "../rule";

const RE_ALPHABETS_NUMBERS = /[A-Za-z0-9]/g;
const FULLWIDTH_OFFSET = 0xfee0;

// Halfwidth katakana (U+FF61-FF9F, common in manga/UI text) is converted to
// its fullwidth form so ﾃﾚﾋﾞ looks up the same headwords as テレビ.
// Conversion is applied per character in the halfwidth-katakana range only
// (whole-string NFKC would fold unrelated characters), then a canonical-
// composition NFC pass combines voiced marks with the preceding letter
// (ｶ + ﾞ -> ガ); NFC performs no compatibility folds.
const RE_HALFWIDTH_KATAKANA = /[\uFF61-\uFF9F]/;
const RE_HALFWIDTH_KATAKANA_G = /[\uFF61-\uFF9F]/g;

const convertHalfwidthKatakana = (s) => s.replace(RE_HALFWIDTH_KATAKANA_G, (c) => c.normalize("NFKC")).normalize("NFC");

const createLookupWordsJa = (sourceStr) => {
  const str = sourceStr
    .substring(0, 40)
    .replaceAll("\u200c", "") // ZERO WIDTH NON-JOINER
    .replace(RE_ALPHABETS_NUMBERS, (s) => String.fromCharCode(s.charCodeAt(0) + FULLWIDTH_OFFSET));

  const result = new UniqList();

  result.push(sourceStr); // Add the original word

  // For halfwidth input, keep both chains: every candidate retains its usual
  // prefix decomposition (show-all-plausible-candidates design), e.g.
  // ﾃﾚﾋ -> ﾃﾚﾋ/ﾃﾚ/ﾃ plus テレビ/テレ/テ.
  const chains = [str];
  if (RE_HALFWIDTH_KATAKANA.test(str)) {
    const converted = convertHalfwidthKatakana(str);
    if (converted !== str) {
      chains.push(converted);
    }
  }

  for (const chain of chains) {
    for (let i = chain.length; i >= 1; i--) {
      const part = chain.substring(0, i);
      result.push(part);

      if (i >= 2) {
        const deinedWords = rule.doJa(part);
        result.merge(deinedWords);
      }
    }
  }
  return result.toArray();
};

export default createLookupWordsJa;
