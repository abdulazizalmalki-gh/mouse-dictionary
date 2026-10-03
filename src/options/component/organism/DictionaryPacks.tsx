/**
 * Mouse Dictionary (https://github.com/wtetsu/mouse-dictionary/)
 * Copyright 2018-present wtetsu
 * Licensed under MIT
 */

import { useEffect, useState } from "react";
import { res } from "../../logic";
import { DICTIONARY_PACKS } from "../../logic/packs";
import { Button } from "../atom/Button";

type Props = {
  busy: boolean;
  selectedPackIds: string[];
  onSync: (packIds: string[]) => void;
};

// Bilingual labels; the extension UI itself supports en/ja only.
const PACK_NAMES: Record<string, { en: string; ja: string }> = {
  "en-ja": { en: "English → Japanese", ja: "英日 (English→日本語)" },
  "en-ar": { en: "English → Arabic", ja: "英亜 (English→العربية)" },
  "ja-ar": { en: "Japanese → Arabic", ja: "日亜 (日本語→العربية)" },
};

export const DictionaryPacks: React.FC<Props> = (props) => {
  const [selected, setSelected] = useState<Set<string>>(new Set(props.selectedPackIds));

  useEffect(() => {
    setSelected(new Set(props.selectedPackIds));
  }, [props.selectedPackIds]);

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelected(next);
  };

  const lang = res.getLang() === "ja" ? "ja" : "en";
  const dirty = selected.size !== props.selectedPackIds.length || props.selectedPackIds.some((id) => !selected.has(id));

  return (
    <div style={{ marginTop: 10 }}>
      <div>
        {DICTIONARY_PACKS.map((pack) => (
          <label key={pack.id} style={{ marginRight: 16, cursor: "pointer", fontSize: "90%" }}>
            <input
              type="checkbox"
              checked={selected.has(pack.id)}
              disabled={props.busy}
              onChange={() => toggle(pack.id)}
            />{" "}
            {PACK_NAMES[pack.id]?.[lang] ?? pack.id}
          </label>
        ))}
      </div>
      <Button
        type="primary"
        text={res.get("applyDictionaryPacks")}
        disabled={props.busy || !dirty}
        onClick={() => props.onSync(Array.from(selected))}
      />
    </div>
  );
};
