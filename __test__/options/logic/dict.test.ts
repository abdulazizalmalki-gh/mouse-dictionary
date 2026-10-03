import { beforeEach, expect, test, vi } from "vitest";
import Chrome from "../../main/chrome";

// dict.ts reads dictionary shards via fetch(chrome.runtime.getURL(...)).
// Serve fake pack files from memory.
const PACK_FILES: Record<string, any> = {
  "/data/dict-en-ar.json": { files: ["/data/dict-en-ar0.json"] },
  "/data/dict-en-ar0.json": { cat: "قِطّ", water: "مَاء" },
  "/data/dict-ja-ar.json": { files: ["/data/dict-ja-ar0.json"] },
  "/data/dict-ja-ar0.json": { 猫: "ネコ", 水: "みず" },
  "/data/dict.json": { files: ["/data/dict0.json"] },
  "/data/dict0.json": { cat: "キャット", dog: "イヌ" },
};

beforeEach(() => {
  global.chrome = new Chrome() as any;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const path = String(url).replace("chrome-extension://test", "");
      const data = PACK_FILES[path];
      return { json: async () => data } as Response;
    }),
  );
});

test("registerPacks merges descriptions when two packs share a headword", async () => {
  const dict = await import("../../../src/options/logic/dict");
  await dict.registerPacks(["en-ja", "en-ar"], () => {});

  const stored = await global.chrome.storage.local.get(["cat", "water", "dog"]);
  expect(stored.cat).toBe("キャット / قِطّ");
  expect(stored.water).toBe("مَاء");
  expect(stored.dog).toBe("イヌ");
});

test("syncInstalledPacks registers new packs and removes unselected ones", async () => {
  const dict = await import("../../../src/options/logic/dict");

  await dict.syncInstalledPacks(["en-ja", "ja-ar"], () => {});
  let stored = await global.chrome.storage.local.get(["cat", "猫"]);
  expect(stored.cat).toBe("キャット");
  expect(stored["猫"]).toBe("ネコ");

  // Drop ja-ar: its keys are removed, en-ja keys are re-registered.
  await dict.syncInstalledPacks(["en-ja"], () => {});
  stored = await global.chrome.storage.local.get(["cat", "猫"]);
  expect(stored["猫"]).toBeUndefined();
  expect(stored.cat).toBe("キャット");
});
