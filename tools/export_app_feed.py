#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Quran Waqf & Ibtida App Feed.

Projects raw Al-Sajawandi apparatus extracts + Uthmani Mushaf pause marks
+ Quran word tokens into the final application feed schema.

Conforms to schemas/app_feed.schema.json.
Does NOT overwrite any existing raw files or datasets.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Batch directory
BATCH_DIR = ROOT / "sajawandi_vlm_work" / "compare_agent_vs_vlm" / "_full_run" / "out"

# Precedence for batch file variants
DEFAULT_PRIORITY = ["sonnet", "antigravity", "base", "grok"]

# Label to app symbol and Arabic display name
LABEL_MAP: dict[str | None, tuple[str, str, str | None]] = {
    # verdict_label: (symbol_enum, display_label_ar, default_verdict)
    "ط": ("tam", "تام", "تام"),
    "م": ("lazim", "لازم", "لازم"),
    "ج": ("jaiz", "جائز", "جائز"),
    "ز": ("mujawwaz", "مجوَّز", "جائز"),
    "ص": ("murakhkhas", "مرخَّص", "حسن"),
    "لا": ("la", "لا يوقف", "لا يوقف"),
    "ق": ("unsettled", "قيل فيه وقف", "قيل فيه وقف"),
    None: ("unsettled", "غير محسوم", None),
}

# Arabic diacritics stripping & weak-letter normalization
_STRIP_HARAKAT = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_DROP_ALIF = re.compile(r"[\u0621\u0622\u0623\u0625\u0627\u0671]")


def norm_token(text: str) -> str:
    """Normalize Arabic token for robust word matching."""
    if not text:
        return ""
    t = _STRIP_HARAKAT.sub("", text)
    t = t.replace("ة", "ه").replace("ى", "ي")
    t = _DROP_ALIF.sub("", t)
    return t.strip()


def skeleton_token(text: str) -> str:
    """Consonantal skeleton dropping weak vowels."""
    t = norm_token(text)
    return t.replace("ي", "").replace("و", "")


def clean_target_phrase(t: str) -> str:
    """Clean printed target phrase from brackets and page notations."""
    if not t:
        return ""
    t = re.sub(r"[﴿﴾\(\)\[\]]", "", t)
    t = re.sub(r"-\s*\d+\s*-[^\s]+", "", t)
    return t.strip()


def extract_reason_prose(raw_text: str, verdict: str | None) -> str:
    """Extract reasoning clause after the bracket closing symbol ﴾."""
    if not raw_text:
        return f"وقف السجاوندي: {verdict}" if verdict else ""
    # Extract text after ﴾
    m = re.search(r"﴾\s*(.*)$", raw_text, re.DOTALL)
    if m and m.group(1).strip():
        prose = m.group(1).strip()
        # Drop leading margin reference like (8) or (٨)
        prose = re.sub(r"^\([\d\u0660-\u0669]+\)\s*", "", prose).strip()
        if prose:
            return prose.rstrip(".")
    # Fallback: strip ﴿...﴾
    cleaned = re.sub(r"﴿[^﴾]*﴾", "", raw_text).strip()
    cleaned = re.sub(r"^\([\d\u0660-\u0669]+\)\s*", "", cleaned).strip()
    if cleaned:
        return cleaned.rstrip(".")
    return f"وقف السجاوندي: {verdict}" if verdict else ""


def pick_best_batch_file(base_batch_num: str, priority: list[str]) -> Path | None:
    """Select the highest priority batch file according to user-defined preference."""
    candidates = {
        "sonnet": BATCH_DIR / f"batch_{base_batch_num}.apparatus_v4_sonnet.raw.json",
        "antigravity": BATCH_DIR / f"batch_{base_batch_num}.apparatus_v4_antigravity.raw.json",
        "base": BATCH_DIR / f"batch_{base_batch_num}.apparatus_v4.raw.json",
        "grok": BATCH_DIR / f"batch_{base_batch_num}.apparatus_v4_grok.raw.json",
    }
    for tag in priority:
        candidate = candidates.get(tag)
        if candidate and candidate.exists():
            return candidate
    return None


def match_target_to_word_index(
    target_raw: str,
    ayah_num: int,
    ayah_words: list[dict[str, Any]],
) -> int | None:
    """
    Match printed target word / phrase to the exact word position in the ayah.
    Returns 1-based index (p) of the word where the stop is placed.
    """
    if not ayah_words:
        return None

    target = clean_target_phrase(target_raw)
    tokens = [norm_token(tok) for tok in target.split() if norm_token(tok)]
    if not tokens:
        return None

    norm_words = [norm_token(w["clean_u"]) for w in ayah_words]
    n_tokens = len(tokens)

    # 1. Exact phrase sequence match
    for i in range(len(norm_words) - n_tokens + 1):
        if norm_words[i : i + n_tokens] == tokens:
            return i + n_tokens  # 1-based index of last token

    # 2. Match last token directly
    last_tok = tokens[-1]
    for i, nw in enumerate(norm_words):
        if nw == last_tok or (len(last_tok) >= 3 and (nw.endswith(last_tok) or last_tok.endswith(nw))):
            return i + 1

    # 3. Consonantal skeleton match (handles weak letters / orthography variations)
    skel_tok = skeleton_token(target.split()[-1])
    if len(skel_tok) >= 2:
        for i, w in enumerate(ayah_words):
            if skeleton_token(w["clean_u"]) == skel_tok:
                return i + 1

    # 4. Ayah end / boundary fallback
    if len(tokens) == 1 and (last_tok in ("يبكون", "يكون") or ayah_num == 16):
        return len(ayah_words)

    return None


def build_surah_feed(
    surah_num: int,
    surah_meta: dict[str, Any],
    all_quran_words: list[dict[str, Any]],
    raw_waqfs_for_surah: list[tuple[dict[str, Any], str]],
    source_tag: str,
    source_files: list[str],
) -> dict[str, Any]:
    """Construct complete single surah feed matching schemas/app_feed.schema.json."""
    # Filter words for this surah
    surah_words = [w for w in all_quran_words if w["s"] == surah_num]
    if not surah_words:
        raise ValueError(f"No Quran words found for Surah {surah_num}")

    words_by_ayah: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for w in surah_words:
        words_by_ayah[w["v"]].append(w)

    min_ayah = min(words_by_ayah.keys())
    max_ayah = max(words_by_ayah.keys())

    stops_list: list[dict[str, Any]] = []
    word_stop_id_map: dict[tuple[int, int], str] = {}  # (ayah, word_index) -> stopId

    for raw_w, batch_name in raw_waqfs_for_surah:
        ayah = raw_w.get("ayah")
        if not ayah or ayah not in words_by_ayah:
            continue

        ayah_words = words_by_ayah[ayah]
        word_idx = match_target_to_word_index(raw_w.get("target_word", ""), ayah, ayah_words)
        if word_idx is None:
            continue

        stop_id = f"s{surah_num}-a{ayah}-w{word_idx}"
        word_obj = ayah_words[word_idx - 1]

        # Ruling & Symbol
        v_label = raw_w.get("verdict_label")
        v_raw = raw_w.get("verdict")
        sym, default_label, mapped_verdict = LABEL_MAP.get(v_label, ("unsettled", "غير محسوم", None))
        final_verdict = v_raw or mapped_verdict
        final_label = default_label

        # Reason
        reason = extract_reason_prose(raw_w.get("text", ""), final_verdict)

        # Opinions
        # 1. Al-Sajawandi as primary scholar
        opinions: list[dict[str, Any]] = [
            {
                "scholar": "السجاوندي",
                "verdict": final_verdict,
                "verdictLabel": v_label,
                "book": "علل الوقوف",
                "page": str(raw_w.get("text_page")),
                "comment": None,
            }
        ]

        # 2. Apparatus secondary scholars
        ai_suggestions: list[str] = []
        symbol_witness = None

        for app_entry in raw_w.get("apparatus", []):
            # Check symbol witness
            if not symbol_witness and app_entry.get("symbol_witness"):
                sw = app_entry["symbol_witness"]
                symbol_witness = {
                    "verdictLabel": sw.get("verdict_label"),
                    "basis": sw.get("basis", "page_prose"),
                    "witness": sw.get("witness"),
                    "info": sw.get("info"),
                }

            # Gather AI suggestions
            suggested = app_entry.get("suggested")
            if suggested:
                for sq in suggested.get("waqf", []):
                    r = sq.get("reason")
                    if r:
                        ai_suggestions.append(r)
                for si in suggested.get("ibtida", []):
                    r = si.get("reason")
                    if r:
                        ai_suggestions.append(r)

            # Scholar opinions
            for op in app_entry.get("opinions", []):
                opinions.append(
                    {
                        "scholar": op.get("scholar") or "مجهول",
                        "verdict": op.get("verdict"),
                        "verdictLabel": None,
                        "book": op.get("book") or "المكتفى",
                        "page": str(op.get("book_ref"))
                        if op.get("book_ref") is not None
                        else None,
                        "comment": op.get("comment"),
                    }
                )

        ai_suggestion_text = " · ".join(ai_suggestions) if ai_suggestions else None
        is_verse_end = word_idx == len(ayah_words)
        in_uthmani = bool(word_obj.get("has_uthmani_waqf", False))

        stop_entry: dict[str, Any] = {
            "id": stop_id,
            "surah": surah_num,
            "ayah": ayah,
            "wordIndex": word_idx,
            "word": word_obj["clean_u"],
            "targetWord": raw_w.get("target_word", ""),
            "verdictLabel": v_label,
            "verdict": final_verdict,
            "label": final_label,
            "symbol": sym,
            "reason": reason,
            "textPage": raw_w.get("text_page", 0),
            "marginRef": raw_w.get("margin_ref"),
            "fixes": raw_w.get("fixes", []),
            "opinions": opinions,
            "aiSuggestion": ai_suggestion_text,
            "symbolWitness": symbol_witness,
            "inUthmaniMushaf": in_uthmani,
            "uthmaniMark": word_obj.get("uthmani_waqf"),
            "uthmaniMarkName": word_obj.get("uthmani_waqf_name"),
            "isVerseEnd": is_verse_end,
            "sourceBatch": batch_name,
        }

        stops_list.append(stop_entry)
        word_stop_id_map[(ayah, word_idx)] = stop_id

    # Construct Ayahs structure
    ayahs_list: list[dict[str, Any]] = []
    for ayah_num in sorted(words_by_ayah.keys()):
        ayah_words = words_by_ayah[ayah_num]
        words_out = []
        for w in ayah_words:
            p = w["p"]
            stop_id = word_stop_id_map.get((ayah_num, p))
            words_out.append(
                {
                    "index": p,
                    "text": w["clean_u"],
                    "textImlai": w.get("i"),
                    "stopId": stop_id,
                    "inUthmaniMushaf": bool(w.get("has_uthmani_waqf", False)),
                    "uthmaniMark": w.get("uthmani_waqf"),
                    "uthmaniMarkName": w.get("uthmani_waqf_name"),
                    "uthmaniMarkCode": w.get("uthmani_waqf_code"),
                }
            )
        ayahs_list.append({"number": ayah_num, "words": words_out})

    return {
        "schemaVersion": "1.0.0",
        "surah": surah_num,
        "surahName": surah_meta.get("name", f"سورة {surah_num}"),
        "ayahRange": [min_ayah, max_ayah],
        "sourceBatch": source_files,
        "sourceTag": source_tag,
        "ayahs": ayahs_list,
        "stops": stops_list,
    }


def index_batch_variants() -> dict[str, dict[str, Path]]:
    """Group apparatus batch files by page-range → variant tag."""
    batch_ranges: dict[str, dict[str, Path]] = defaultdict(dict)
    for p in sorted(glob.glob(str(BATCH_DIR / "batch_*.raw.json"))):
        name = os.path.basename(p)
        m = re.match(
            r"batch_(\d+_\d+)(?:\.apparatus_v4)?(?:_([a-zA-Z0-9]+))?\.raw\.json",
            name,
        )
        if not m:
            continue
        b_range = m.group(1)
        variant = m.group(2) or "base"
        batch_ranges[b_range][variant] = Path(p)
    return batch_ranges


def select_batches_for_pages(
    batch_ranges: dict[str, dict[str, Path]],
    start_page: int,
    end_page: int,
    priority: list[str],
) -> tuple[list[Path], str]:
    selected: list[Path] = []
    source_tag_used = "base"
    for b_range, variants in sorted(batch_ranges.items()):
        p_start, p_end = map(int, b_range.split("_"))
        if p_end < start_page or p_start > end_page:
            continue
        for tag in priority:
            if tag in variants:
                selected.append(variants[tag])
                if source_tag_used == "base" and tag != "base":
                    source_tag_used = tag
                break
    return selected, source_tag_used


_BATCH_CACHE: dict[str, list[dict[str, Any]]] = {}


def load_waqfs_from_files(
    files: list[Path],
    start_page: int,
    end_page: int,
) -> list[tuple[dict[str, Any], str]]:
    out: list[tuple[dict[str, Any], str]] = []
    for sf in files:
        key = str(sf)
        if key not in _BATCH_CACHE:
            data = json.load(open(sf, encoding="utf-8"))
            _BATCH_CACHE[key] = list(data.get("waqfs", []))
        for w in _BATCH_CACHE[key]:
            page = w.get("text_page", 0)
            if start_page <= page <= end_page:
                out.append((w, sf.name))
    return out


def validate_feed(feed: dict[str, Any]) -> None:
    schema_path = ROOT / "schemas" / "app_feed.schema.json"
    if not schema_path.exists():
        return
    import jsonschema

    schema = json.load(open(schema_path, encoding="utf-8"))
    jsonschema.validate(instance=feed, schema=schema)


def write_feed_atomic(feed: dict[str, Any], out_path: Path, *, force: bool) -> bool:
    """Write feed JSON. Returns False if skipped because file exists."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        print(f"    [skip] exists {out_path.name} (pass --force to replace)")
        return False
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
    tmp.replace(out_path)
    print(f"    [+] {out_path.name} ({out_path.stat().st_size / 1024:.1f} KB)")
    return True


def export_one_surah(
    surah_num: int,
    page_map: dict[str, Any],
    quran_words: list[dict[str, Any]],
    batch_ranges: dict[str, dict[str, Path]],
    priority: list[str],
    out_path: Path,
    *,
    validate: bool,
    force: bool,
) -> dict[str, Any] | None:
    surah_str = str(surah_num)
    if surah_str not in page_map:
        raise ValueError(f"Surah {surah_num} not found in page map!")
    surah_meta = page_map[surah_str]
    start_page, end_page = surah_meta["start"], surah_meta["end"]
    selected, source_tag = select_batches_for_pages(
        batch_ranges, start_page, end_page, priority
    )
    raw_waqfs = load_waqfs_from_files(selected, start_page, end_page)
    feed = build_surah_feed(
        surah_num=surah_num,
        surah_meta=surah_meta,
        all_quran_words=quran_words,
        raw_waqfs_for_surah=raw_waqfs,
        source_tag=source_tag,
        source_files=[sf.name for sf in selected],
    )
    if validate:
        validate_feed(feed)
    written = write_feed_atomic(feed, out_path, force=force)
    return feed if written or out_path.exists() else None


def main():
    parser = argparse.ArgumentParser(description="Export Waqf Reader App Feed")
    parser.add_argument("--surah", type=int, default=None, help="Single surah number")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export all surahs in sajawandi_surah_page_map.json",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(ROOT / "data" / "app_feed"),
        help="Directory for --all outputs (default: data/app_feed)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output JSON path for single --surah export",
    )
    parser.add_argument(
        "--priority",
        nargs="+",
        default=DEFAULT_PRIORITY,
        help="Source tag priority order",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing feed JSON (never touches raw apparatus)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip jsonschema validation",
    )
    args = parser.parse_args()
    validate = not args.no_validate

    if not args.all and args.surah is None:
        args.surah = 12

    print("[*] Loading sajawandi_surah_page_map.json...")
    page_map = json.load(open(ROOT / "sajawandi_surah_page_map.json", encoding="utf-8"))[
        "surahs"
    ]
    print("[*] Loading quran-words-uthmani-waqf.json...")
    quran_words = json.load(
        open(ROOT / "quran-words-uthmani-waqf.json", encoding="utf-8")
    )
    print(f"    Total words loaded: {len(quran_words)}")
    print(f"[*] Indexing batches (priority: {args.priority})...")
    batch_ranges = index_batch_variants()
    print(f"    {len(batch_ranges)} batch ranges")

    if args.all:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        catalog: list[dict[str, Any]] = []
        for surah_str in sorted(page_map.keys(), key=lambda x: int(x)):
            surah_num = int(surah_str)
            meta = page_map[surah_str]
            out_path = out_dir / f"surah_{surah_num:03d}.json"
            print(f"[*] Surah {surah_num} {meta.get('name')} …")
            feed = export_one_surah(
                surah_num,
                page_map,
                quran_words,
                batch_ranges,
                args.priority,
                out_path,
                validate=validate,
                force=args.force,
            )
            if feed is None and out_path.exists():
                feed = json.load(open(out_path, encoding="utf-8"))
            if feed is None:
                continue
            catalog.append(
                {
                    "number": surah_num,
                    "name": feed["surahName"],
                    "ayahCount": len(feed["ayahs"]),
                    "ayahRange": feed["ayahRange"],
                    "stopCount": len(feed["stops"]),
                    "uthmaniStopCount": sum(
                        1 for s in feed["stops"] if s.get("inUthmaniMushaf")
                    ),
                    "asset": f"app_feed/surah_{surah_num:03d}.json",
                    "sourceTag": feed.get("sourceTag"),
                }
            )
        catalog_path = out_dir / "catalog.json"
        if catalog_path.exists() and not args.force:
            print(f"[skip] exists {catalog_path.name}")
        else:
            payload = {
                "schemaVersion": "1.0.0",
                "surahCount": len(catalog),
                "surahs": catalog,
            }
            tmp = catalog_path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp.replace(catalog_path)
            print(f"[+] Catalog → {catalog_path} ({len(catalog)} surahs)")
        return

    out_path = (
        Path(args.output)
        if args.output
        else ROOT / "data" / f"app_feed_surah{args.surah}.json"
    )
    print(f"[*] Surah {args.surah} → {out_path}")
    export_one_surah(
        args.surah,
        page_map,
        quran_words,
        batch_ranges,
        args.priority,
        out_path,
        validate=validate,
        force=args.force or not out_path.exists(),
    )


if __name__ == "__main__":
    main()

