#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge pass-3 suggestions into a NEW file and prove pass 1/2 data is untouched.

usage: merge_apparatus_pass3.py <pass12.json> <suggest.json> <out.json>

- never overwrites an existing out file
- attaches suggestion.suggested to apparatus[] item matched by
  (ayah, target_word, margin_ref, text_page)
- verifies: out minus all `suggested` keys == pass12 exactly
"""
import copy
import json
import sys
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def strip_suggested(data):
    d = copy.deepcopy(data)
    for w in d.get("waqfs", []):
        for a in w.get("apparatus", []):
            a.pop("suggested", None)
    return d


def main():
    p12, psug, pout = map(Path, sys.argv[1:4])
    if pout.exists():
        sys.exit(f"refuse to overwrite {pout}")
    base = load(p12)
    sug = load(psug)
    merged = copy.deepcopy(base)

    index = {}
    # match at NOTE level: (ayah, target_word, note.margin_ref, note.text_page)
    for w in merged.get("waqfs", []):
        for a in w.get("apparatus", []):
            index[(w["ayah"], w["target_word"], a.get("margin_ref"), a.get("text_page"))] = a

    attached, unmatched = 0, []
    for s in sug.get("suggestions", []):
        key = (s["ayah"], s["target_word"], s.get("margin_ref"), s.get("text_page"))
        note = index.get(key)
        if note is None:
            unmatched.append(key)
            continue
        note["suggested"] = s["suggested"]
        attached += 1

    # guard: pass 1/2 data must be identical after removing `suggested`
    if strip_suggested(merged) != strip_suggested(base):
        sys.exit("GUARD FAILED: pass 1/2 data changed")
    for w in base.get("waqfs", []):
        for a in w.get("apparatus", []):
            assert "suggested" not in a, "base already had suggested"

    pout.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"attached={attached} unmatched={len(unmatched)} guard=OK -> {pout}")
    for k in unmatched:
        print("  unmatched", k)


if __name__ == "__main__":
    main()
