#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pack a base_app_feed surah into ~250-word extraction batches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FEED_DIR = Path(
    r"D:\AI_Projects\jamharah_waqf_scraper\app_workspace\data\base_app_feed"
)


def words_per_ayah(surah: int) -> list[tuple[int, int]]:
    feed = FEED_DIR / f"surah_{surah:03d}.json"
    data = json.loads(feed.read_text(encoding="utf-8"))
    ayahs = data.get("ayahs") or data.get("verses") or data.get("entries") or data
    out: list[tuple[int, int]] = []
    if isinstance(ayahs, dict):
        for k in sorted(ayahs, key=lambda x: int(x)):
            a = ayahs[k]
            words = a.get("words") or a.get("uthmaniWords") or a.get("wordList") or []
            n = len(words)
            out.append((int(k), n))
        return out
    if isinstance(ayahs, list):
        for i, a in enumerate(ayahs, 1):
            if not isinstance(a, dict):
                out.append((i, 0))
                continue
            num = int(a.get("ayah") or a.get("number") or a.get("ayahNumber") or i)
            words = a.get("words") or a.get("uthmaniWords") or a.get("wordList") or []
            # some feeds store text and separate word arrays under tokens
            if not words and isinstance(a.get("text"), str):
                words = a["text"].split()
            n = len(words) if not isinstance(words, dict) else len(words)
            out.append((num, n))
        return out
    raise SystemExit(f"unknown feed shape keys={list(data)[:30]}")


def pack(words: list[tuple[int, int]], target: int = 250, min_soft: int = 180) -> list[tuple[int, int, int, int]]:
    batches: list[tuple[int, int, int, int]] = []
    i = 0
    while i < len(words):
        start = words[i][0]
        total = 0
        j = i
        while j < len(words):
            nxt = total + words[j][1]
            if total >= min_soft and nxt > target + 40:
                break
            if total > 0 and nxt > target + 80:
                break
            total = nxt
            j += 1
            if total >= target and j > i + 1:
                break
        if j == i:
            j = i + 1
            total = words[i][1]
        end = words[j - 1][0]
        batches.append((start, end, total, j - i))
        i = j
    return batches


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--target", type=int, default=250)
    args = ap.parse_args()
    words = words_per_ayah(args.surah)
    print(f"surah={args.surah} ayahs={len(words)} total_words={sum(n for _, n in words)}")
    print("first3", words[:3], "last3", words[-3:])
    # dump keys of first ayah for diagnostics if word counts look wrong
    if sum(n for _, n in words) < 100:
        feed = json.loads((FEED_DIR / f"surah_{args.surah:03d}.json").read_text(encoding="utf-8"))
        print("top keys", list(feed)[:40])
        sample = feed.get("ayahs") or feed.get("verses") or feed
        if isinstance(sample, list) and sample:
            print("ayah0 keys", list(sample[0])[:40])
        elif isinstance(sample, dict):
            k0 = next(iter(sample))
            print("ayah0 keys", list(sample[k0])[:40] if isinstance(sample[k0], dict) else type(sample[k0]))

    batches = pack(words, target=args.target)
    print(f"\n{len(batches)} batches:")
    for s, e, w, na in batches:
        bid = f"s{args.surah:03d}_a{s:03d}_{e:03d}"
        print(f'    ("{bid}", {s}, {e}),  # {na} ayahs, {w} words')
    print("sum words", sum(b[2] for b in batches))


if __name__ == "__main__":
    main()
