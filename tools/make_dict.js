/**
 * Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)
 * Copyright 2018-present wtetsu
 * Licensed under MIT
 */

// Make dictionary data and metadata.

const fs = require("node:fs");
const path = require("node:path");
const json5 = require("json5");
const glob = require("fast-glob");

const main = (options, outputDirPath) => {
  const args = process.argv.slice(2);
  const force = args.includes("--force");

  const skip = allFilesExist(options.to, options.split, outputDirPath) && !force;
  if (skip) {
    const outPath = path.join(outputDirPath, `${options.to}.json`);
    console.info(`⏭️ Skipped(Already exists): ${outPath}`);
    return;
  }

  generateDictData(options, outputDirPath);
};

const generateDictData = (options, outputDirPath) => {
  fs.mkdirSync(outputDirPath, { recursive: true });

  const data = uniteJsonFiles(options.from);
  const outFilePaths = splitDataAndWrite(data, options.split, options.to, outputDirPath);

  const distInformation = { files: outFilePaths };
  const outputFilePath = path.join(outputDirPath, `${options.to}.json`);
  fs.writeFileSync(outputFilePath, JSON.stringify(distInformation), "utf-8");
  console.info(`✅ Generated: ${outputFilePath}`);
};

const splitDataAndWrite = (data, split, to, outputDirPath) => {
  const keys = Object.keys(data);
  keys.sort();
  const unit = (keys.length * 1.0) / split;

  let nextThreshold = unit;
  let outData = {};

  const outFiles = [];
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    outData[key] = data[key];
    if (i + 1 >= nextThreshold || i === keys.length - 1) {
      const outJson = JSON.stringify(outData);
      const outFileName = `/${to}${outFiles.length}.json`;
      const outPath = path.join(outputDirPath, outFileName);
      fs.writeFileSync(outPath, outJson, "utf-8");
      console.info(`✅ Generated: ${outPath}`);

      outData = {};
      outFiles.push(outFileName);
      nextThreshold += unit;
    }
  }
  return outFiles;
};

const allFilesExist = (to, split, outputDirPath) => {
  if (!fs.existsSync(path.join(outputDirPath, `${to}.json`))) {
    return false;
  }

  for (let i = 0; i < split; i++) {
    const outPath = path.join(outputDirPath, `${to}${i}.json`);
    if (!fs.existsSync(outPath)) {
      return false;
    }
  }
  return true;
};

const uniteJsonFiles = (fileGlobList) => {
  const resultData = {};
  for (const fileGlob of fileGlobList) {
    for (const entry of glob.sync(fileGlob)) {
      const json = fs.readFileSync(entry, "utf-8");
      const data = json5.parse(json);
      Object.assign(resultData, data);
    }
  }
  return resultData;
};

const DICTIONARY_PACKS = [
  { from: ["data/dict/[a-z].json5"], to: "data/dict", split: 10 },
  { from: ["data/dict-en-ar/[0-9][0-9].json5"], to: "data/dict-en-ar", split: 4 },
  { from: ["data/dict-ja-ar/[0-9][0-9].json5"], to: "data/dict-ja-ar", split: 20 },
];

if (require.main === module) {
  for (const pack of DICTIONARY_PACKS) {
    main(pack, "static/gen");
  }
}

module.exports = { DICTIONARY_PACKS, main };
