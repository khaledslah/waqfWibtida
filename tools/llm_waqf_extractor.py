#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grounded Pure-LLM Waqf Extractor, Boundary Synchronizer & Validator.

1. `--prepare`: Exports the exact Uthmani/Imlai word table, raw 5-scholar statements,
   and `boundaryContext` (lookbehind/lookahead words + neighboring scholar sections)
   for a Surah / Ayah range into `data/llm_prototype/s{surah:03d}_a{start:03d}_{end:03d}_input.json`.
2. `--validate`: Validates an LLM-produced extraction JSON against the full Surah (and cross-surah)
   Uthmani word table, records `boundaryFlags` and out-of-range stops in `boundary_ledger.json`,
   and generates a side-by-side comparison against the regex exporter.
3. `--apply-to-feed`: Patches the validated LLM stops for that Ayah range directly into
   `WaqfReader_Grok/assets/app_feed/surah_{surah:03d}.json` and `build/flutter_assets/...`,
   while syncing any cross-boundary stops with `boundary_ledger.json` without clobbering neighbor batches.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE_ROOT = Path(r"d:\AI_Projects\waqfWibtida2")
SCRAPER_ROOT = Path(r"D:\AI_Projects\jamharah_waqf_scraper")
JAMHARAH_PARSED_DIR = SCRAPER_ROOT / "fixed_copy" / "data" / "parsed"
QAT_FIXED_DIR = SCRAPER_ROOT / "data" / "qat_itinaf" / "fixed_by_surah"
BASE_FEED_DIR = SCRAPER_ROOT / "app_workspace" / "data" / "base_app_feed"
REGEX_FEED_DIR = WORKSPACE_ROOT / "WaqfReader_Grok" / "assets" / "app_feed"
BUILD_FEED_DIR = WORKSPACE_ROOT / "WaqfReader_Grok" / "build" / "flutter_assets" / "assets" / "app_feed"
PROTOTYPE_DIR = WORKSPACE_ROOT / "data" / "llm_prototype"
BOUNDARY_LEDGER_PATH = PROTOTYPE_DIR / "boundary_ledger.json"

SCHOLAR_ID_TO_AR = {
    "al_sajawandi": ("السجاوندي", "علل الوقوف"),
    "al_dani": ("الداني", "المكتفى"),
    "ibn_al_anbari": ("ابن الأنباري", "إيضاح الوقف والابتداء"),
    "al_ashmuni": ("الأشموني", "منار الهدى"),
    "al_nahhas": ("النحاس", "القطع والائتناف"),
}

ALLOWED_VERDICTS = {
    "لازم": ("م", "lazim"),
    "تام": ("ط", "tam"),
    "كاف": ("ج", "jaiz"),
    "حسن": ("ص", "murakhkhas"),
    "صالح": ("ز", "mujawwaz"),
    "مفهوم": ("ز", "mujawwaz"),
    "جائز": ("ج", "jaiz"),
    "قيل فيه وقف": ("ق", "jaiz"),
    "لا يوقف": ("لا", "la"),
}

SAJAWANDI_SYM_MAP = {
    "م": ("لازم", "م", "lazim"),
    "ط": ("تام", "ط", "tam"),
    "ج": ("جائز", "ج", "jaiz"),
    "ز": ("جائز", "ز", "mujawwaz"),
    "ص": ("حسن", "ص", "murakhkhas"),
    "لا": ("لا يوقف", "لا", "la"),
    "ق": ("قيل فيه وقف", "ق", "jaiz"),
}


def _load_surah_word_lookup(surah: int) -> dict[tuple[int, int], dict[str, Any]]:
    base_data = json.loads((BASE_FEED_DIR / f"surah_{surah:03d}.json").read_text(encoding="utf-8"))
    lookup: dict[tuple[int, int], dict[str, Any]] = {}
    for ay_obj in base_data["ayahs"]:
        ay_num = ay_obj["number"]
        words = ay_obj["words"]
        for w in words:
            lookup[(ay_num, w["index"])] = {
                "surah": surah,
                "ayah": ay_num,
                "wordIndex": w["index"],
                "wordUthmani": w["text"],
                "wordImlai": w.get("textImlai") or w["text"],
                "isVerseEnd": w["index"] == len(words),
                "inUthmaniMushaf": bool(w.get("inUthmaniMushaf", False)),
            }
    return lookup


def prepare_section_input(surah: int, start_ayah: int, end_ayah: int, context_margin: int = 3) -> Path:
    PROTOTYPE_DIR.mkdir(parents=True, exist_ok=True)
    base_data = json.loads((BASE_FEED_DIR / f"surah_{surah:03d}.json").read_text(encoding="utf-8"))
    jam_data = json.loads((JAMHARAH_PARSED_DIR / f"surah_{surah:03d}.json").read_text(encoding="utf-8"))
    qat_path = QAT_FIXED_DIR / f"surah_{surah:03d}.json"
    qat_data = json.loads(qat_path.read_text(encoding="utf-8")) if qat_path.exists() else {"entries": []}

    ayah_words: list[dict[str, Any]] = []
    prev_words: list[dict[str, Any]] = []
    next_words: list[dict[str, Any]] = []

    for ay_obj in base_data["ayahs"]:
        ay_num = ay_obj["number"]
        words = ay_obj["words"]
        target_list: list[dict[str, Any]] | None = None
        if start_ayah <= ay_num <= end_ayah:
            target_list = ayah_words
        elif max(1, start_ayah - context_margin) <= ay_num < start_ayah:
            target_list = prev_words
        elif end_ayah < ay_num <= end_ayah + context_margin:
            target_list = next_words
        if target_list is not None:
            for w in words:
                target_list.append({
                    "ayah": ay_num,
                    "wordIndex": w["index"],
                    "wordUthmani": w["text"],
                    "wordImlai": w.get("textImlai") or w["text"],
                    "isVerseEnd": w["index"] == len(words),
                    "inUthmaniMushaf": bool(w.get("inUthmaniMushaf", False)),
                })

    all_parsed_sections: list[dict[str, Any]] = []
    for sec in jam_data.get("sections", []):
        ay_nums = sec.get("ayahNumbers") or []
        if not ay_nums and sec.get("ayahRange"):
            r0, r1 = sec["ayahRange"]
            ay_nums = list(range(r0, r1 + 1))
        if not ay_nums:
            continue
        s_min, s_max = min(ay_nums), max(ay_nums)
        stmts = []
        for st in sec.get("scholarStatements", []):
            sid = st["scholarId"]
            sch_ar, default_book = SCHOLAR_ID_TO_AR.get(sid, (sid, ""))
            stmts.append({
                "scholarId": sid,
                "scholar": sch_ar,
                "book": st.get("book") or default_book,
                "page": st.get("pageRef"),
                "text": st.get("text", ""),
            })
        all_parsed_sections.append({
            "ayahRange": [s_min, s_max],
            "postId": sec.get("postId"),
            "scholarStatements": stmts,
        })

    jam_sections: list[dict[str, Any]] = []
    prev_sections: list[dict[str, Any]] = []
    next_sections: list[dict[str, Any]] = []
    for idx_s, s_obj in enumerate(all_parsed_sections):
        s_min, s_max = s_obj["ayahRange"]
        if not (s_max < start_ayah or s_min > end_ayah):
            jam_sections.append(s_obj)
        elif s_max < start_ayah and s_max >= start_ayah - context_margin:
            prev_sections.append(s_obj)
        elif s_min > end_ayah and s_min <= end_ayah + context_margin:
            next_sections.append(s_obj)

    nahhas_entries: list[dict[str, Any]] = []
    prev_nahhas: list[dict[str, Any]] = []
    next_nahhas: list[dict[str, Any]] = []
    for ent in qat_data.get("entries", []):
        ent_obj = {
            "scholarId": "al_nahhas",
            "scholar": "النحاس",
            "book": "القطع والائتناف",
            "page": f"آية {ent['ayah']}",
            "ayah": ent["ayah"],
            "text": ent["text"],
        }
        if start_ayah <= ent["ayah"] <= end_ayah:
            nahhas_entries.append(ent_obj)
        elif max(1, start_ayah - context_margin) <= ent["ayah"] < start_ayah:
            prev_nahhas.append(ent_obj)
        elif end_ayah < ent["ayah"] <= end_ayah + context_margin:
            next_nahhas.append(ent_obj)

    # Format `ayahWords`, `prevWords`, `nextWords` compactly (1 line per ayah) so input JSON is < 250 lines
    # and fits in a single `view_file` call (800-line limit), while still supporting full validation.
    def _compact_words_by_ayah(w_list: list[dict[str, Any]]) -> dict[str, str]:
        by_ay: dict[int, list[str]] = {}
        for w in w_list:
            mark = " [رأس آية]" if w["isVerseEnd"] else (" [مصحف]" if w["inUthmaniMushaf"] else "")
            by_ay.setdefault(w["ayah"], []).append(f"{w['wordIndex']}:{w['wordUthmani']}{mark}")
        return {str(ay): " | ".join(toks) for ay, toks in sorted(by_ay.items())}

    payload = {
        "surah": surah,
        "surahName": base_data["surahName"],
        "ayahRange": [start_ayah, end_ayah],
        "ayahWordsCompact": _compact_words_by_ayah(ayah_words),
        "jamharahSections": jam_sections,
        "nahhasEntries": nahhas_entries,
        "boundaryContext": {
            "prevWordsCompact": _compact_words_by_ayah(prev_words),
            "nextWordsCompact": _compact_words_by_ayah(next_words),
            "prevSections": prev_sections[-1:],
            "nextSections": next_sections[:1],
            "prevNahhasEntries": prev_nahhas[-2:],
            "nextNahhasEntries": next_nahhas[:2],
        },
    }
    out_path = PROTOTYPE_DIR / f"s{surah:03d}_a{start_ayah:03d}_{end_ayah:03d}_input.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    line_cnt = len(out_path.read_text(encoding="utf-8").splitlines())
    print(
        f"Prepared input at: {out_path} ({line_cnt} lines, "
        f"{len(ayah_words)} words, {len(jam_sections)} Jamharah sections, {len(nahhas_entries)} Nahhas entries)"
    )
    return out_path


def _parse_sajawandi_page(raw: str | None) -> int | None:
    if not raw:
        return None
    s = str(raw).strip()
    m_vol = re.match(r"^\s*([1-9])\s*/\s*(\d+)", s)
    if m_vol:
        val = int(m_vol.group(2))
    else:
        m = re.search(r"(\d+)", s)
        if not m:
            return None
        val = int(m.group(1))
    return val if 1 <= val <= 1300 else None


def _text_page_for_opinions(opinions: list[dict[str, Any]]) -> int | None:
    for op in opinions:
        sch = op.get("scholar") or ""
        bk = op.get("book") or ""
        if "السجاوندي" in sch or "علل الوقوف" in bk:
            tp = _parse_sajawandi_page(op.get("page"))
            if tp is not None:
                return tp
    return None


def _sync_catalog_counts(modified_surahs: set[int]) -> None:
    cat_path = REGEX_FEED_DIR / "catalog.json"
    if not cat_path.exists():
        return
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    changed = False
    for entry in catalog.get("surahs", []):
        s_num = entry.get("number")
        if s_num not in modified_surahs:
            continue
        feed_path = REGEX_FEED_DIR / f"surah_{s_num:03d}.json"
        if not feed_path.exists():
            continue
        sd = json.loads(feed_path.read_text(encoding="utf-8"))
        actual_stops = len(sd.get("stops", []))
        actual_uthmani = sum(1 for st in sd.get("stops", []) if st.get("inUthmaniMushaf"))
        if entry.get("stopCount") != actual_stops or entry.get("uthmaniStopCount") != actual_uthmani:
            entry["stopCount"] = actual_stops
            entry["uthmaniStopCount"] = actual_uthmani
            changed = True
    if changed:
        out_txt = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        for dest_dir in [REGEX_FEED_DIR, BUILD_FEED_DIR]:
            if dest_dir.exists():
                (dest_dir / "catalog.json").write_text(out_txt, encoding="utf-8")


def _validate_and_normalize_demos(
    raw_demos: Any, stop_id: str, scholar: str, validation_errors: list[str]
) -> list[dict[str, Any]] | None:
    if raw_demos is None:
        return None
    if not isinstance(raw_demos, list):
        validation_errors.append(f"demosAndMeanings must be list or null at {stop_id} ({scholar})")
        return None
    req_str = ["waqfDemo", "ibtidaDemo", "meaningAtWaqf", "meaningAtIbtida", "meaningIfConnected"]
    cleaned: list[dict[str, Any]] = []
    for idx_d, d in enumerate(raw_demos):
        if not isinstance(d, dict):
            validation_errors.append(f"demosAndMeanings[{idx_d}] not object at {stop_id} ({scholar})")
            continue
        v_raw = d.get("verdict")
        v_norm = "صالح" if v_raw == "مفهوم" else v_raw
        if v_norm not in ALLOWED_VERDICTS:
            validation_errors.append(f"Unknown demosAndMeanings verdict {v_raw!r} at {stop_id} ({scholar})")
            continue
        for span_key in ("waqfSegmentWords", "ibtidaSegmentWords"):
            sp = d.get(span_key)
            if sp is not None:
                if (
                    not isinstance(sp, list)
                    or len(sp) != 2
                    or not all(isinstance(n, int) and n >= 1 for n in sp)
                    or sp[0] > sp[1]
                ):
                    validation_errors.append(
                        f"Invalid {span_key}={sp!r} at {stop_id} ({scholar})"
                    )
        missing_txt = [k for k in req_str if not isinstance(d.get(k), str) or not d[k].strip()]
        if missing_txt:
            validation_errors.append(
                f"Missing/empty demosAndMeanings fields {missing_txt} at {stop_id} ({scholar})"
            )
            continue
        entry: dict[str, Any] = {
            "verdict": v_norm,
            "isQila": bool(d.get("isQila", False)),
        }
        if d.get("attributedTo"):
            entry["attributedTo"] = str(d["attributedTo"]).strip()
        entry["waqfSegmentWords"] = d.get("waqfSegmentWords")
        entry["ibtidaSegmentWords"] = d.get("ibtidaSegmentWords")
        for k in req_str:
            entry[k] = d[k].strip()
        cleaned.append(entry)
    return cleaned or None


def _merge_opinion_into_stop(stop_obj: dict[str, Any], op_obj: dict[str, Any]) -> None:
    scholar = op_obj["scholar"]
    existing_op = next((o for o in stop_obj["opinions"] if o["scholar"] == scholar), None)
    if existing_op is None:
        if scholar == "السجاوندي":
            stop_obj["opinions"].insert(0, op_obj)
        else:
            stop_obj["opinions"].append(op_obj)
    else:
        for v_i, lbl_i, sym_i, q_i in zip(
            op_obj["verdict"], op_obj["verdictLabel"], op_obj["symbol"], op_obj["isQila"]
        ):
            if v_i not in existing_op["verdict"]:
                existing_op["verdict"].append(v_i)
                existing_op["verdictLabel"].append(lbl_i)
                existing_op["symbol"].append(sym_i)
                existing_op["isQila"].append(q_i)
        if not existing_op.get("page") and op_obj.get("page"):
            existing_op["page"] = op_obj["page"]
        if op_obj.get("comment"):
            prev_c = existing_op.get("comment") or ""
            if not prev_c:
                existing_op["comment"] = op_obj["comment"]
            elif op_obj["comment"] not in prev_c and prev_c not in op_obj["comment"]:
                existing_op["comment"] = f"{prev_c}\n{op_obj['comment']}"
            elif len(op_obj["comment"]) > len(prev_c):
                existing_op["comment"] = op_obj["comment"]
        if "demosAndMeanings" in op_obj:
            new_demos = op_obj.get("demosAndMeanings")
            if new_demos:
                prev_demos = existing_op.get("demosAndMeanings")
                if not prev_demos:
                    existing_op["demosAndMeanings"] = list(new_demos)
                else:
                    seen_keys = {(d.get("verdict"), bool(d.get("isQila")), d.get("attributedTo")) for d in prev_demos}
                    for d in new_demos:
                        dk = (d.get("verdict"), bool(d.get("isQila")), d.get("attributedTo"))
                        if dk not in seen_keys:
                            prev_demos.append(d)
                            seen_keys.add(dk)
            elif "demosAndMeanings" not in existing_op:
                existing_op["demosAndMeanings"] = None
    tp = _text_page_for_opinions(stop_obj["opinions"])
    if tp is not None:
        stop_obj["textPage"] = tp


def _load_boundary_ledger() -> dict[str, Any]:
    if BOUNDARY_LEDGER_PATH.exists():
        try:
            return json.loads(BOUNDARY_LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"batches": {}, "crossBoundaryOpinions": []}


def _save_boundary_ledger(ledger: dict[str, Any]) -> None:
    PROTOTYPE_DIR.mkdir(parents=True, exist_ok=True)
    BOUNDARY_LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_and_compare(
    surah: int, start_ayah: int, end_ayah: int, llm_json_path: Path, apply_to_feed: bool = False
) -> None:
    batch_id = f"s{surah:03d}_a{start_ayah:03d}_{end_ayah:03d}"
    input_path = PROTOTYPE_DIR / f"{batch_id}_input.json"
    if not input_path.exists():
        prepare_section_input(surah, start_ayah, end_ayah)
    llm_data = json.loads(llm_json_path.read_text(encoding="utf-8"))
    regex_feed = json.loads((REGEX_FEED_DIR / f"surah_{surah:03d}.json").read_text(encoding="utf-8"))

    surah_word_cache: dict[int, dict[tuple[int, int], dict[str, Any]]] = {
        surah: _load_surah_word_lookup(surah)
    }

    stops_by_surah_pos: dict[tuple[int, int, int], dict[str, Any]] = {}
    out_of_range_records: list[dict[str, Any]] = []
    typo_records: list[dict[str, Any]] = []
    validation_errors: list[str] = []

    for item in llm_data.get("extractions", []):
        target_surah = int(item.get("surah") or surah)
        if target_surah not in surah_word_cache:
            surah_word_cache[target_surah] = _load_surah_word_lookup(target_surah)
        word_lookup = surah_word_cache[target_surah]

        pos = (int(item["ayah"]), int(item["wordIndex"]))
        if pos not in word_lookup:
            validation_errors.append(
                f"Invalid (surah, ayah, wordIndex)=({target_surah}, {pos[0]}, {pos[1]}) "
                f"for {item.get('scholar')} target={item.get('targetWord')}"
            )
            continue
        w_info = word_lookup[pos]
        stop_id = f"s{target_surah}-a{pos[0]}-w{pos[1]}"
        scholar = item["scholar"]
        book = item.get("book") or dict(SCHOLAR_ID_TO_AR.values()).get(scholar, "علل الوقوف")
        page = item.get("page")
        raw_verdicts = item.get("verdicts") or ["جائز"]
        raw_qila = item.get("isQila") or [False] * len(raw_verdicts)
        raw_sym = item.get("sajawandiSymbol")

        if item.get("typoDetected"):
            typo_records.append({
                "stopId": stop_id,
                "scholar": scholar,
                "typoDetected": item["typoDetected"],
            })

        verdicts: list[str] = []
        labels: list[str] = []
        symbols: list[str] = []
        qila_flags: list[bool] = []

        for idx_v, v in enumerate(raw_verdicts):
            v_norm = "صالح" if v == "مفهوم" else v
            if v_norm not in ALLOWED_VERDICTS:
                validation_errors.append(f"Unknown verdict {v!r} at {stop_id} ({scholar})")
                continue
            if scholar == "السجاوندي" and raw_sym in SAJAWANDI_SYM_MAP and idx_v == 0:
                _, lbl, sym = SAJAWANDI_SYM_MAP[raw_sym]
            else:
                lbl, sym = ALLOWED_VERDICTS[v_norm]
            verdicts.append(v_norm)
            labels.append(lbl)
            symbols.append(sym)
            qila_flags.append(bool(raw_qila[idx_v]) if idx_v < len(raw_qila) else False)

        if not verdicts:
            continue

        raw_tw = item.get("targetWord") or w_info["wordUthmani"]
        if unicodedata.normalize("NFC", raw_tw) == unicodedata.normalize("NFC", w_info["wordUthmani"]):
            raw_tw = w_info["wordUthmani"]
        op_obj = {
            "scholar": scholar,
            "targetWord": raw_tw,
            "verdict": verdicts,
            "verdictLabel": labels,
            "symbol": symbols,
            "isQila": qila_flags,
            "book": book,
            "page": page,
            "comment": (item.get("comment") or "").strip() or None,
        }
        if "demosAndMeanings" in item:
            op_obj["demosAndMeanings"] = _validate_and_normalize_demos(
                item.get("demosAndMeanings"), stop_id, scholar, validation_errors
            )

        s_pos = (target_surah, pos[0], pos[1])
        is_out_of_range = (target_surah != surah) or not (start_ayah <= pos[0] <= end_ayah)
        if is_out_of_range:
            out_of_range_records.append({
                "fromBatch": batch_id,
                "surah": target_surah,
                "ayah": pos[0],
                "wordIndex": pos[1],
                "stopId": stop_id,
                "word": w_info["wordUthmani"],
                "inUthmaniMushaf": w_info["inUthmaniMushaf"],
                "isVerseEnd": w_info["isVerseEnd"],
                "opinion": op_obj,
            })

        if s_pos not in stops_by_surah_pos:
            stops_by_surah_pos[s_pos] = {
                "id": stop_id,
                "surah": target_surah,
                "ayah": pos[0],
                "wordIndex": pos[1],
                "word": w_info["wordUthmani"],
                "textPage": _text_page_for_opinions([op_obj]),
                "marginRef": None,
                "fixes": [],
                "opinions": [op_obj],
                "aiSuggestion": None,
                "symbolWitness": None,
                "inUthmaniMushaf": w_info["inUthmaniMushaf"],
                "uthmaniMark": None,
                "uthmaniMarkName": None,
                "isVerseEnd": w_info["isVerseEnd"],
                "sourceBatch": "llm_grounded_v1",
            }
        else:
            _merge_opinion_into_stop(stops_by_surah_pos[s_pos], op_obj)

    print(f"Validation errors: {len(validation_errors)}")
    for err in validation_errors:
        print("  ERROR:", err)

    in_range_stops = {
        (ay, wi): st
        for (s_num, ay, wi), st in stops_by_surah_pos.items()
        if s_num == surah and start_ayah <= ay <= end_ayah
    }

    # Update boundary ledger
    ledger = _load_boundary_ledger()
    boundary_flags = llm_data.get("boundaryFlags") or {}
    if out_of_range_records and not boundary_flags.get("outOfRangeStopsEmitted"):
        boundary_flags["outOfRangeStopsEmitted"] = [r["stopId"] for r in out_of_range_records]
    ledger["batches"][batch_id] = {
        "surah": surah,
        "ayahRange": [start_ayah, end_ayah],
        "llmFile": str(llm_json_path.name),
        "inRangeStopsCount": len(in_range_stops),
        "outOfRangeStopsCount": len(out_of_range_records),
        "typosDetectedCount": len(typo_records),
        "typosDetected": typo_records,
        "boundaryFlags": boundary_flags,
    }
    ledger["crossBoundaryOpinions"] = [
        r for r in ledger.get("crossBoundaryOpinions", []) if r.get("fromBatch") != batch_id
    ] + out_of_range_records
    _save_boundary_ledger(ledger)

    # Compare against regex feed for start_ayah..end_ayah
    regex_stops = {
        (st["ayah"], st["wordIndex"]): st
        for st in regex_feed["stops"]
        if start_ayah <= st["ayah"] <= end_ayah
    }
    word_lookup_main = surah_word_cache[surah]
    all_positions = sorted(set(regex_stops.keys()) | set(in_range_stops.keys()))
    diff_lines: list[str] = [
        f"# Side-by-Side Comparison: Pure-LLM vs Regex (Surah {surah}, Ayahs {start_ayah}–{end_ayah})\n"
    ]
    diff_count = 0
    for pos in all_positions:
        r_st = regex_stops.get(pos)
        l_st = in_range_stops.get(pos)
        w_text = word_lookup_main[pos]["wordUthmani"]
        r_ops = {o["scholar"]: o for o in (r_st["opinions"] if r_st else [])}
        l_ops = {o["scholar"]: o for o in (l_st["opinions"] if l_st else [])}
        scholars = sorted(set(r_ops.keys()) | set(l_ops.keys()))
        pos_diffs = []
        for sch in scholars:
            ro = r_ops.get(sch)
            lo = l_ops.get(sch)
            if ro and not lo:
                pos_diffs.append(
                    f"- **{sch}**: Regex had `{ro['verdict']}` (`{ro['targetWord']}`), LLM omitted (false/non-stop in regex or missed)."
                )
            elif lo and not ro:
                pos_diffs.append(
                    f"- **{sch}**: **LLM recovered** `{lo['verdict']}` (`{lo['targetWord']}`) — missed by Regex!\n  - Comment: `{lo.get('comment')}`"
                )
            elif ro and lo:
                if ro["verdict"] != lo["verdict"] or (ro.get("comment") or "") != (lo.get("comment") or ""):
                    pos_diffs.append(
                        f"- **{sch}**:\n"
                        f"  - **Regex**: verdict=`{ro['verdict']}`, target=`{ro['targetWord']}`\n"
                        f"    - Comment: `{(ro.get('comment') or '')[:220]}`\n"
                        f"  - **LLM**: verdict=`{lo['verdict']}`, target=`{lo['targetWord']}`\n"
                        f"    - Comment: `{(lo.get('comment') or '')[:220]}`"
                    )
        if pos_diffs:
            diff_count += 1
            diff_lines.append(f"## `s{surah}-a{pos[0]}-w{pos[1]}` — ﴿{w_text}﴾ (Ayah {pos[0]}, Word {pos[1]})")
            diff_lines.extend(pos_diffs)
            diff_lines.append("")

    report_path = PROTOTYPE_DIR / f"{batch_id}_comparison.md"
    report_path.write_text("\n".join(diff_lines), encoding="utf-8")
    print(
        f"Wrote comparison report to {report_path} "
        f"({len(in_range_stops)} in-range LLM stops + {len(out_of_range_records)} cross-boundary stops "
        f"vs {len(regex_stops)} regex stops, {len(typo_records)} typos recorded)"
    )

    if apply_to_feed and not validation_errors:
        # Also merge any cross-boundary opinions from OTHER batches that target `surah` in `start_ayah..end_ayah`
        for cb in ledger.get("crossBoundaryOpinions", []):
            if cb["surah"] == surah and start_ayah <= cb["ayah"] <= end_ayah:
                pos = (cb["ayah"], cb["wordIndex"])
                if pos not in in_range_stops:
                    in_range_stops[pos] = {
                        "id": cb["stopId"],
                        "surah": surah,
                        "ayah": cb["ayah"],
                        "wordIndex": cb["wordIndex"],
                        "word": cb["word"],
                        "textPage": _text_page_for_opinions([cb["opinion"]]),
                        "marginRef": None,
                        "fixes": [],
                        "opinions": [cb["opinion"]],
                        "aiSuggestion": None,
                        "symbolWitness": None,
                        "inUthmaniMushaf": cb["inUthmaniMushaf"],
                        "uthmaniMark": None,
                        "uthmaniMarkName": None,
                        "isVerseEnd": cb["isVerseEnd"],
                        "sourceBatch": "llm_grounded_v1",
                    }
                else:
                    _merge_opinion_into_stop(in_range_stops[pos], cb["opinion"])

        kept_stops = [
            st for st in regex_feed["stops"] if not (start_ayah <= st["ayah"] <= end_ayah)
        ]
        new_stops = kept_stops + [in_range_stops[k] for k in sorted(in_range_stops.keys())]
        new_stops.sort(key=lambda s: (s["ayah"], s["wordIndex"]))
        regex_feed["stops"] = new_stops
        stop_id_by_pos = {(s["ayah"], s["wordIndex"]): s["id"] for s in new_stops}
        for ay_obj in regex_feed["ayahs"]:
            ay_n = ay_obj["number"]
            if start_ayah <= ay_n <= end_ayah:
                for w_obj in ay_obj["words"]:
                    w_obj["stopId"] = stop_id_by_pos.get((ay_n, w_obj.get("index", 0)))

        for dest_dir in [REGEX_FEED_DIR, BUILD_FEED_DIR]:
            if dest_dir.exists():
                (dest_dir / f"surah_{surah:03d}.json").write_text(
                    json.dumps(regex_feed, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        # Upsert any out-of-range stops emitted by THIS batch into their target surah/ayah
        by_target_surah: dict[int, list[dict[str, Any]]] = {}
        for cb in out_of_range_records:
            by_target_surah.setdefault(cb["surah"], []).append(cb)

        for t_surah, cb_list in by_target_surah.items():
            t_feed_path = REGEX_FEED_DIR / f"surah_{t_surah:03d}.json"
            t_feed = json.loads(t_feed_path.read_text(encoding="utf-8"))
            t_stops_map = {(s["ayah"], s["wordIndex"]): s for s in t_feed["stops"]}
            for cb in cb_list:
                pos = (cb["ayah"], cb["wordIndex"])
                if pos not in t_stops_map:
                    t_stops_map[pos] = {
                        "id": cb["stopId"],
                        "surah": t_surah,
                        "ayah": cb["ayah"],
                        "wordIndex": cb["wordIndex"],
                        "word": cb["word"],
                        "textPage": _text_page_for_opinions([cb["opinion"]]),
                        "marginRef": None,
                        "fixes": [],
                        "opinions": [cb["opinion"]],
                        "aiSuggestion": None,
                        "symbolWitness": None,
                        "inUthmaniMushaf": cb["inUthmaniMushaf"],
                        "uthmaniMark": None,
                        "uthmaniMarkName": None,
                        "isVerseEnd": cb["isVerseEnd"],
                        "sourceBatch": "llm_grounded_v1",
                    }
                else:
                    _merge_opinion_into_stop(t_stops_map[pos], cb["opinion"])
            t_new_stops = [t_stops_map[k] for k in sorted(t_stops_map.keys())]
            t_feed["stops"] = t_new_stops
            t_stop_ids = {(s["ayah"], s["wordIndex"]): s["id"] for s in t_new_stops}
            for ay_obj in t_feed["ayahs"]:
                ay_n = ay_obj["number"]
                for w_obj in ay_obj["words"]:
                    w_obj["stopId"] = t_stop_ids.get((ay_n, w_obj.get("index", 0)))
            for dest_dir in [REGEX_FEED_DIR, BUILD_FEED_DIR]:
                if dest_dir.exists():
                    (dest_dir / f"surah_{t_surah:03d}.json").write_text(
                        json.dumps(t_feed, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

        _sync_catalog_counts({surah} | set(by_target_surah.keys()))
        print(
            f"Applied LLM stops for Surah {surah} Ayahs {start_ayah}..{end_ayah} "
            f"(+{len(out_of_range_records)} cross-boundary stops synced via boundary_ledger.json)!"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surah", type=int, default=2)
    parser.add_argument("--start-ayah", type=int, default=1)
    parser.add_argument("--end-ayah", type=int, default=10)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--validate", type=str, help="Path to LLM extraction JSON")
    parser.add_argument("--apply-to-feed", action="store_true")
    args = parser.parse_args()

    if args.prepare:
        prepare_section_input(args.surah, args.start_ayah, args.end_ayah)
    if args.validate:
        validate_and_compare(
            args.surah,
            args.start_ayah,
            args.end_ayah,
            Path(args.validate),
            apply_to_feed=args.apply_to_feed,
        )


if __name__ == "__main__":
    main()
