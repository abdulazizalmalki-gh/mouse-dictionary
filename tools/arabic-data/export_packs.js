/**
 * Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)
 * Copyright 2018-present wtetsu
 * Licensed under MIT
 *
 * Export the extracted JSON (cache/en-ar.json, cache/ja-ar.json produced by
 * the Python extractors in this directory) into repository data directories.
 * Keys are sorted; each source file holds up to CHUNK entries so that git
 * diffs stay localized. tools/make_dict.js then merges these directories and
 * splits them into lookup shards at build time.
 */

const fs = require("node:fs");
const path = require("node:path");

const CHUNK = 4000;

const exportPack = (inPath, outDir) => {
  const data = JSON.parse(fs.readFileSync(inPath, "utf-8"));
  const keys = Object.keys(data).sort();

  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(outDir, { recursive: true });

  let files = 0;
  for (let i = 0; i < keys.length; i += CHUNK) {
    const chunk = {};
    for (const k of keys.slice(i, i + CHUNK)) {
      chunk[k] = data[k];
    }
    const out = path.join(outDir, `${String(files).padStart(2, "0")}.json5`);
    fs.writeFileSync(out, JSON.stringify(chunk, null, 1) + "\n", "utf-8");
    files += 1;
  }
  console.info(`✅ ${path.basename(inPath)} -> ${path.basename(outDir)} (${keys.length} entries, ${files} files)`);
};

const root = path.join(__dirname, "..", "..");
exportPack(path.join(__dirname, "cache", "en-ar.json"), path.join(root, "data", "dict-en-ar"));
exportPack(path.join(__dirname, "cache", "ja-ar.json"), path.join(root, "data", "dict-ja-ar"));
