import { describe, expect, test } from "vitest";
import {
  DEFAULT_PACK_IDS,
  DICTIONARY_PACKS,
  mergeDescriptions,
  packIdsFromSettings,
} from "../../../src/options/logic/packs";

describe("mergeDescriptions", () => {
  test("returns incoming when there is no existing value", () => {
    expect(mergeDescriptions(undefined, "كتابه")).toBe("كتابه");
  });

  test("returns existing when incoming is empty", () => {
    expect(mergeDescriptions("existing", "")).toBe("existing");
  });

  test("returns existing when identical", () => {
    expect(mergeDescriptions("same", "same")).toBe("same");
  });

  test("joins different descriptions with separator", () => {
    expect(mergeDescriptions("AAA", "BBB")).toBe("AAA / BBB");
  });

  test("skips incoming when it is already contained in existing", () => {
    expect(mergeDescriptions("AAA / BBB", "BBB")).toBe("AAA / BBB");
  });

  test("prefers incoming when it contains existing entirely", () => {
    expect(mergeDescriptions("BBB", "AAA / BBB")).toBe("AAA / BBB");
  });
});

describe("packIdsFromSettings", () => {
  test("unknown or empty selections fall back to defaults", () => {
    expect(packIdsFromSettings(undefined)).toEqual(DEFAULT_PACK_IDS);
    expect(packIdsFromSettings([])).toEqual(DEFAULT_PACK_IDS);
    expect(packIdsFromSettings(["no-such-pack"])).toEqual(DEFAULT_PACK_IDS);
  });

  test("valid ids pass through in order", () => {
    expect(packIdsFromSettings(["en-ar", "ja-ar"])).toEqual(["en-ar", "ja-ar"]);
  });

  test("invalid ids are filtered out, valid ones kept", () => {
    expect(packIdsFromSettings(["en-ar", "bogus"])).toEqual(["en-ar"]);
  });
});

describe("DICTIONARY_PACKS registry", () => {
  test("contains the three language packs with metadata files", () => {
    const ids = DICTIONARY_PACKS.map((p) => p.id);
    expect(ids).toEqual(expect.arrayContaining(["en-ja", "en-ar", "ja-ar"]));
    for (const pack of DICTIONARY_PACKS) {
      expect(pack.metaFile).toMatch(/^\/data\/dict(-en-ar|-ja-ar)?\.json$/);
    }
  });

  test("defaults are all registered", () => {
    for (const id of DEFAULT_PACK_IDS) {
      expect(DICTIONARY_PACKS.some((p) => p.id === id)).toBe(true);
    }
  });
});
