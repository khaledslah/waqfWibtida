#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive 114-Surah Deep Semantic & Structural Scanner.
Finds every passage across Surahs 1..114 where the current regex feed
has a false stop, wrong ayah/word attachment, negated-verdict bug,
missed stop, or OCR typo, so we can fix and validate all 114 surahs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE_ROOT = Path(r"d:\AI_Projects\waqfWibtida2")
SCRAPER_ROOT = Path(r"D:\AI_Projects\jamharah_waqf_scraper")
JAMHARAH_PARSED_DIR = SCRAPER_ROOT / "fixed_copy" / "data" / "parsed"
QAT_FIXED_DIR = SCRAPER_ROOT / "data" / "qat_itinaf" / "fixed_by_surah"
FEED_DIR = WORKSPACE_ROOT / "WaqfReader_Grok" / "assets" / "app_feed"

DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def norm_ar(text: str) -> str:
    s = DIACRITICS_RE.sub("", text or "")
    s = (
        s.replace("ٱ", "ا")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ى", "ي")
        .replace("ة", "ه")
    )
    return re.sub(r"[^\u0621-\u064A0-9\s]", "", s).strip()


def norm_keep_hamza(text: str) -> str:
    """Keep إ vs أ distinct so إلا (exception) is not confused with ألا (tanbih)."""
    s = DIACRITICS_RE.sub("", text or "")
    return s.strip()


def run_deep_scan() -> None:
    results: dict[str, list[dict[str, Any]]] = {
        "1_negated_verdict_false_positives": [],
        "2_stop_before_illa_exception": [],
        "3_wrong_ayah_attachment_candidates": [],
        "4_nahhas_zero_stop_entries": [],
        "5_nahhas_qiraat_wakadha_backward_or_midverse": [],
        "6_missed_explicit_waqf_clauses": [],
        "7_ocr_verdict_typos": [],
    }

    for surah in range(1, 115):
        feed = json.loads((FEED_DIR / f"surah_{surah:03d}.json").read_text(encoding="utf-8"))
        jam_p = JAMHARAH_PARSED_DIR / f"surah_{surah:03d}.json"
        qat_p = QAT_FIXED_DIR / f"surah_{surah:03d}.json"
        jam = json.loads(jam_p.read_text(encoding="utf-8")) if jam_p.exists() else {"sections": []}
        qat = json.loads(qat_p.read_text(encoding="utf-8")) if qat_p.exists() else {"entries": []}

        word_map: dict[tuple[int, int], dict[str, Any]] = {}
        ayah_words_norm: dict[int, set[str]] = {}
        for ay in feed["ayahs"]:
            an = ay["number"]
            w_set = set()
            for w in ay["words"]:
                word_map[(an, w["index"])] = w
                w_set.add(norm_ar(w["text"]))
            ayah_words_norm[an] = w_set

        scholar_stops_by_ayah: dict[tuple[str, int], list[tuple[int, dict[str, Any], dict[str, Any]]]] = {}
        for st in feed["stops"]:
            ay = st["ayah"]
            wi = st["wordIndex"]
            for op in st["opinions"]:
                scholar_stops_by_ayah.setdefault((op["scholar"], ay), []).append((wi, st, op))

        # Check 1 & 2 on existing stops
        for st in feed["stops"]:
            ay = st["ayah"]
            wi = st["wordIndex"]
            nxt = word_map.get((ay, wi + 1))
            nxt_raw = norm_keep_hamza(nxt["text"]) if nxt else ""

            for op in st["opinions"]:
                comm = op.get("comment") or ""
                verds = op["verdict"]

                # Check 1: `ليس بقطع كاف` / `ليس بوقف كاف` / `ليس بقطع تام` where positive verdict was falsely added
                if "لا يوقف" in verds and len(verds) > 1:
                    if re.search(r"ليس\s+ب(?:قطع|وقف)\s+(?:كاف|تام|حسن)", comm):
                        # Check if there is genuinely another positive opinion in the comment
                        rem = re.sub(r"ليس\s+ب(?:قطع|وقف)\s+(?:كاف|تام|حسن)", "", comm)
                        if not re.search(r"\b(?:وهو|فأما|وقال|وقيل|تم|تمام|كاف|كافي|حسن|صالح|جائز)\b", rem):
                            results["1_negated_verdict_false_positives"].append({
                                "surah": surah,
                                "ayah": ay,
                                "wordIndex": wi,
                                "word": st["word"],
                                "scholar": op["scholar"],
                                "verdict": verds,
                                "comment": comm,
                            })

                # Check 2: Stop immediately before `إِلَّا` (with hamza below alif: إ) with positive verdict
                if nxt_raw in ("إلا", "إلآ") and verds != ["لا يوقف"]:
                    results["2_stop_before_illa_exception"].append({
                        "surah": surah,
                        "ayah": ay,
                        "wordIndex": wi,
                        "word": st["word"],
                        "nextWord": nxt["text"],
                        "scholar": op["scholar"],
                        "verdict": verds,
                        "targetWord": op.get("targetWord"),
                        "comment": comm[:220],
                    })

        # Check 3: Bracketed [ayah] out of order in Ibn al-Anbari / Al-Dani / Al-Sajawandi
        for sec in jam.get("sections", []):
            ay_nums = sec.get("ayahNumbers") or []
            if not ay_nums and sec.get("ayahRange"):
                r0, r1 = sec["ayahRange"]
                ay_nums = list(range(r0, r1 + 1))
            if not ay_nums:
                continue
            s_min, s_max = min(ay_nums), max(ay_nums)

            for st_obj in sec.get("scholarStatements", []):
                sid = st_obj["scholarId"]
                sch_ar = {
                    "al_sajawandi": "السجاوندي",
                    "al_dani": "الداني",
                    "ibn_al_anbari": "ابن الأنباري",
                    "al_ashmuni": "الأشموني",
                }.get(sid, sid)
                txt = st_obj.get("text") or ""

                # Check [ayah] brackets without colon (so we skip [البقرة: 10] cross-surah refs)
                b_matches = []
                for m_b in re.finditer(r"(?:«([^»]+)»|\(([^)]+)\)|\{([^}]+)\}|(\S+))\s*\[(\d+)\]", txt):
                    target_str = m_b.group(1) or m_b.group(2) or m_b.group(3) or m_b.group(4) or ""
                    ay_b = int(m_b.group(5))
                    if s_min <= ay_b <= s_max:
                        b_matches.append((target_str.strip(), ay_b, m_b.start()))
                for idx_b in range(1, len(b_matches)):
                    prev_t, prev_a, _ = b_matches[idx_b - 1]
                    curr_t, curr_a, pos_c = b_matches[idx_b]
                    if curr_a > prev_a + 1 or curr_a < prev_a:
                        # Check if the target word actually exists in curr_a
                        last_w = norm_ar(curr_t.split()[-1]) if curr_t.split() else ""
                        if last_w and last_w not in ayah_words_norm.get(curr_a, set()):
                            results["3_wrong_ayah_attachment_candidates"].append({
                                "surah": surah,
                                "scholar": sch_ar,
                                "sectionRange": [s_min, s_max],
                                "target": curr_t,
                                "bracketAyah": curr_a,
                                "prevAyah": prev_a,
                                "context": txt[max(0, pos_c - 60): min(len(txt), pos_c + 120)].replace("\n", " "),
                            })

                # Check 6: Explicit `الوقف على ...` / `ولا يتم الوقف على ...` / `ولا يجوز الوقف على ...`
                sec_extracted_words = set()
                for a_n in range(max(1, s_min - 1), s_max + 2):
                    for _, st_e, _ in scholar_stops_by_ayah.get((sch_ar, a_n), []):
                        sec_extracted_words.add(norm_ar(st_e["word"]))

                for m_w in re.finditer(
                    r"(?:الوقف\s+على|ويوقف\s+على|ولا\s+يوقف\s+على|ولا\s+يجوز\s+الوقف\s+على|ولا\s+يتم\s+الوقف\s+على|ولا\s+يحسن\s+الوقف\s+على|القطع\s+على)\s*(?:قوله\s*:\s*)?(?:«([^»]{1,45})»|\(([^)]{1,45})\)|\{([^}]{1,45})\}|([^\s،.؛:«»(){}]{2,20}))",
                    txt,
                ):
                    t_phrase = (m_w.group(1) or m_w.group(2) or m_w.group(3) or m_w.group(4) or "").strip()
                    t_phrase_clean = re.sub(r"\(\d+\)|\[\d+\]|\d+", "", t_phrase)
                    t_phrase_clean = re.sub(r"\b(?:الأول|الثاني|الثالث|الأولى|الثانية|الأخير|الأخيرة)\b", "", t_phrase_clean).strip()
                    t_words = [norm_ar(w) for w in t_phrase_clean.split() if norm_ar(w)]
                    if not t_words:
                        continue
                    last_w = t_words[-1]
                    if last_w in (
                        "قوله", "ان", "ما", "اي", "هذا", "ذلك", "راس", "رؤوس", "الاول", "الثاني", "الايه",
                        "عليه", "عليها", "عليهما", "عليهن", "منه", "منها", "فيه", "فيها", "به", "بها",
                        "مرفوع", "منصوب", "مجرور", "مجزوم", "الاسم", "الفعل", "الحرف", "اخر", "اول",
                        "الاستثناء", "النداء", "الشرط", "الجواب", "المضاف", "النعت", "المنعوت", "البسمله", "التسميه", "التعوذ",
                    ):
                        continue
                    last_w_bare = last_w[2:] if last_w.startswith("ال") and len(last_w) >= 5 else last_w
                    matched = False
                    for ew in sec_extracted_words:
                        ew_bare = ew[2:] if ew.startswith("ال") and len(ew) >= 5 else ew
                        if (
                            ew == last_w
                            or ew_bare == last_w_bare
                            or ew.endswith(last_w)
                            or last_w.endswith(ew)
                            or (len(last_w_bare) >= 3 and (ew.endswith(last_w_bare) or ew_bare.startswith(last_w_bare)))
                        ):
                            matched = True
                            break
                    if not matched:
                        results["6_missed_explicit_waqf_clauses"].append({
                            "surah": surah,
                            "scholar": sch_ar,
                            "sectionRange": [s_min, s_max],
                            "targetPhrase": t_phrase,
                            "context": txt[max(0, m_w.start() - 20): min(len(txt), m_w.end() + 100)].replace("\n", " "),
                        })

                # Check 7: Whole-word OCR verdict typos
                for m_t in re.finditer(
                    r"(?:الوقف\s+عل[ىيه]\s+[^\s،.]+\s+(?:نعم|كان|حس|عام)\b|وهو\s+وقف\s+(?:نعم|كان|حس|عام)\b|فالوقف\s+(?:عليه\s+)?(?:نعم|كان|حس|عام)\b)",
                    txt,
                ):
                    results["7_ocr_verdict_typos"].append({
                        "surah": surah,
                        "scholar": sch_ar,
                        "sectionRange": [s_min, s_max],
                        "match": m_t.group(0),
                    })

        # Check 4 & 5: Al-Nahhas entries
        for ent in qat.get("entries", []):
            ay = ent["ayah"]
            txt = ent.get("text") or ""
            n_ops = scholar_stops_by_ayah.get(("النحاس", ay), [])
            if not n_ops and re.search(r"\b(?:كاف|كافي|تام|تمام|حسن|صالح|قبيح|لا يوقف|لا يتم|ليس بقطع|يقطع)\b", txt):
                results["4_nahhas_zero_stop_entries"].append({
                    "surah": surah,
                    "ayah": ay,
                    "text": txt,
                })
            # Check `وكذا (` where there are multiple stops in the ayah and Qira'at is discussed
            if "وكذا" in txt and len(n_ops) >= 2 and re.search(r"(?:قراءة|قرأ|قرئ|يقرأ|الألف|والوقف واحد|المعنى واحد)", txt):
                results["5_nahhas_qiraat_wakadha_backward_or_midverse"].append({
                    "surah": surah,
                    "ayah": ay,
                    "stops": [(wi, st["word"], op["verdict"], op.get("targetWord")) for wi, st, op in n_ops],
                    "text": txt,
                })

    for k, v in results.items():
        print(f"{k}: {len(v)}")
    out_p = WORKSPACE_ROOT / "data" / "llm_prototype" / "deep_114_surahs_scan.json"
    out_p.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved deep scan to {out_p}")


if __name__ == "__main__":
    run_deep_scan()
