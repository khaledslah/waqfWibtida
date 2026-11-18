#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan and apply cross-ayah waqf / ibtida segment patches across app_feed JSONs.

Usage:
  python tools/gemini_parallel/fix_cross_ayah_spans.py --scan
  python tools/gemini_parallel/fix_cross_ayah_spans.py --apply data/llm_prototype/cross_ayah_patches.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"d:\AI_Projects\waqfWibtida2")
SCRATCH = Path(
    r"C:\Users\Khaled\.gemini\antigravity\brain\8ff04f0d-c5f6-4bce-b7e6-c4129c706c84\scratch"
)
APP_FEED_DIR = ROOT / "WaqfReader_Grok" / "assets" / "app_feed"
BUILD_FEED_DIR = (
    ROOT / "WaqfReader_Grok" / "build" / "flutter_assets" / "assets" / "app_feed"
)
CANDIDATES_OUT = ROOT / "data" / "llm_prototype" / "cross_ayah_candidates.json"
CHECKPOINT_OUT = ROOT / "data" / "llm_prototype" / "cross_ayah_results.jsonl"

STOPWORDS_AR = {
    "من", "في", "على", "الى", "عن", "ما", "لا", "ان", "كان", "قال", "قوله",
    "وهو", "هي", "هم", "ثم", "او", "بل", "قد", "لم", "لن", "الا", "هذا",
    "ذلك", "التي", "الذي", "الذين", "الله", "رب", "كل", "بين", "لكم", "لهم",
    "منكم", "منهم", "فيها", "عليه", "عليهم", "به", "بها", "فيه", "كما",
}

BACKWARD_CUE_RE = re.compile(
    r"ما قبله|ما قبلها|بما قبل|الآية السابق|الآيه السابق|الآية التي قبل|"
    r"رأس الآية قبله|آخر الآية قبل|وصلها بما قبل|مرتبط بالسابق|"
    r"تعلق\s+[^.،؛]*قبل|متعلق\s+[^.،؛]*قبل|تعلقه\s+[^.،؛]*قبل|صلة\s+لـ?"
)
FORWARD_CUE_RE = re.compile(
    r"الآية التالي|ما بعده|ما بعدها|بما بعد|الآية بعد|رأس الآية بعد|"
    r"أول الآية التالي|يتصل بالآية|تعلق\s+[^.،؛]*بعد|متعلق\s+[^.،؛]*بعد|تعلقه\s+[^.،؛]*بعد"
)
JAWAB_START_WORDS = {"كلا", "بلي", "نعم"}


def norm_ar(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "")
    s = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]", "", s)
    for src, dst in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي"), ("ة", "ه")):
        s = s.replace(src, dst)
    return s


def compact_words(words: list[dict[str, Any]]) -> str:
    return " ".join(f"{w['index']}:{w['text']}" for w in words)


def scan_candidates(app_feed_dir: Path = APP_FEED_DIR) -> dict[str, Any]:
    """Identify stops/demos likely requiring cross-ayah waqf or ibtida spans."""
    candidates: list[dict[str, Any]] = []
    stats: dict[str, int] = {
        "surahsScanned": 0,
        "backwardHighScore": 0,
        "forwardHighScore": 0,
        "commentStarOrAyahSep": 0,
        "demoStarOrAyahSep": 0,
        "jawabParticleAtStart": 0,
        "alreadyCrossAyah": 0,
    }

    for fpath in sorted(app_feed_dir.glob("surah_*.json")):
        data = json.loads(fpath.read_text(encoding="utf-8"))
        stats["surahsScanned"] += 1
        s_num = int(data["surah"] if isinstance(data["surah"], int) else data["surah"]["number"])
        ayah_words: dict[int, list[dict[str, Any]]] = {
            int(a["number"]): list(a.get("words") or []) for a in data.get("ayahs", [])
        }
        stops_by_id = {s["id"]: s for s in data.get("stops", [])}

        for stop in data.get("stops", []):
            ay = int(stop["ayah"])
            wi = int(stop["wordIndex"])
            cur_words = ayah_words.get(ay, [])
            mw = len(cur_words)
            is_end = bool(stop.get("isVerseEnd")) or wi == mw
            stop_norm = norm_ar(stop.get("word", ""))

            prev_words = ayah_words.get(ay - 1, [])
            next_words = ayah_words.get(ay + 1, [])

            # Distinctive tail words in Ayah N-1 not appearing in Ayah N
            cur_norm_set = {norm_ar(w["text"]) for w in cur_words}
            prev_tail = [
                (w["index"], norm_ar(w["text"]))
                for w in prev_words[-15:]
                if len(norm_ar(w["text"])) >= 4
                and norm_ar(w["text"]) not in STOPWORDS_AR
                and norm_ar(w["text"]) not in cur_norm_set
            ]
            next_head = [
                (w["index"], norm_ar(w["text"]))
                for w in next_words[:12]
                if len(norm_ar(w["text"])) >= 4
                and norm_ar(w["text"]) not in STOPWORDS_AR
                and norm_ar(w["text"]) not in cur_norm_set
            ]

            for op in stop.get("opinions", []):
                scholar = op.get("scholar", "")
                cmt = op.get("comment") or ""
                cmt_norm = norm_ar(cmt)
                demos = op.get("demosAndMeanings") or []
                for idx_d, dm in enumerate(demos):
                    if dm.get("waqfStartAyah") or dm.get("ibtidaEndAyah") or dm.get("ibtidaStartAyah"):
                        stats["alreadyCrossAyah"] += 1
                        continue

                    ws = dm.get("waqfSegmentWords")
                    ib = dm.get("ibtidaSegmentWords")
                    wd_txt = dm.get("waqfDemo") or ""
                    ibd_txt = dm.get("ibtidaDemo") or ""
                    mw_txt = f"{dm.get('meaningAtWaqf', '')} {dm.get('meaningIfConnected', '')}"
                    mi_txt = f"{dm.get('meaningAtIbtida', '')} {dm.get('meaningIfConnected', '')}"

                    reasons: list[str] = []
                    score = 0

                    # 1. Explicit * or ۝ ayah separator anywhere inside raw comment (very strong signal)
                    if "*" in cmt or "۝" in cmt:
                        score += 3
                        reasons.append("comment_has_star_or_ayah_sep")
                        stats["commentStarOrAyahSep"] += 1

                    # 2. Existing demo text itself already spans across ayahs (*, ۝, وتصلها بقوله)
                    # Guard each side by prev_words / next_words so last-ayah next-surah previews don't misfire.
                    has_wd_cross = bool(prev_words) and ("*" in wd_txt or "۝" in wd_txt)
                    has_ib_cross = bool(next_words) and (
                        "*" in ibd_txt or "۝" in ibd_txt or "وتصلها بقوله" in ibd_txt
                    )
                    if has_wd_cross or has_ib_cross:
                        score += 4
                        reasons.append("demo_has_star_or_ayah_sep")
                        stats["demoStarOrAyahSep"] += 1

                    # 3. Jawab / radd particles at very start of ayah (كلا / بلى / نعم)
                    if prev_words and wi <= 2 and stop_norm in JAWAB_START_WORDS:
                        score += 2
                        reasons.append("jawab_particle_at_ayah_start")
                        stats["jawabParticleAtStart"] += 1

                    # 4. Backward waqf candidate (ws hits word 1 on ayah > 1, or waqfDemo itself already crosses)
                    if prev_words and (
                        (isinstance(ws, list) and len(ws) >= 2 and ws[0] == 1)
                        or has_wd_cross
                    ):
                        matched_prev = [
                            (idx_w, txt_w)
                            for idx_w, txt_w in prev_tail
                            if re.search(
                                rf"(?:^|[^\u0621-\u064A])(?:و|ف|ب|ل)?{re.escape(txt_w)}(?:$|[^\u0621-\u064A])",
                                cmt_norm,
                            )
                        ]
                        has_bwd_cue = bool(BACKWARD_CUE_RE.search(cmt) or BACKWARD_CUE_RE.search(mw_txt))
                        if wi <= 8 and (matched_prev or has_bwd_cue):
                            score += 3 if matched_prev else 2
                            reasons.append("early_in_ayah_backward_ref")
                        elif matched_prev and (has_bwd_cue or len(matched_prev) >= 2):
                            score += 2
                            reasons.append("prev_word_and_cue")
                        elif has_bwd_cue:
                            score += 2
                            reasons.append("backward_cue_in_text")

                        if matched_prev:
                            reasons.append(
                                "cites_prev_words=" + ",".join(f"{i}:{w}" for i, w in matched_prev[:4])
                            )

                    # 5. Forward ibtida candidate (mid-ayah reaching end OR book comment forward cue)
                    if next_words and (
                        (isinstance(ib, list) and len(ib) >= 2 and ib[1] == mw)
                        or is_end
                    ):
                        matched_next = [
                            (idx_w, txt_w)
                            for idx_w, txt_w in next_head
                            if re.search(
                                rf"(?:^|[^\u0621-\u064A])(?:و|ف|ب|ل)?{re.escape(txt_w)}(?:$|[^\u0621-\u064A])",
                                cmt_norm,
                            )
                        ]
                        has_fwd_cmt = bool(FORWARD_CUE_RE.search(cmt))
                        has_fwd_all = has_fwd_cmt or bool(FORWARD_CUE_RE.search(mi_txt))
                        if not is_end and has_fwd_all:
                            score += 2 if matched_next else 2
                            reasons.append("mid_ayah_ibtida_reaches_end_with_cue")
                        elif is_end and (has_fwd_cmt or matched_next):
                            score += 2 if (has_fwd_cmt and matched_next) else (2 if has_fwd_cmt else 1)
                            if has_fwd_cmt:
                                reasons.append("verse_end_comment_forward_cue")
                        if matched_next:
                            reasons.append(
                                "cites_next_words=" + ",".join(f"{i}:{w}" for i, w in matched_next[:4])
                            )

                    if score >= 2:
                        if any("backward" in r or "prev_word" in r or "jawab" in r for r in reasons):
                            stats["backwardHighScore"] += 1
                        if any("ibtida" in r or "forward" in r for r in reasons):
                            stats["forwardHighScore"] += 1

                        cand: dict[str, Any] = {
                            "surah": s_num,
                            "stopId": stop["id"],
                            "ayah": ay,
                            "wordIndex": wi,
                            "stopWord": stop["word"],
                            "scholar": scholar,
                            "demoIndex": idx_d,
                            "verdict": dm.get("verdict"),
                            "isQila": bool(dm.get("isQila", False)),
                            "score": score,
                            "reasons": reasons,
                            "comment": cmt,
                            "existingDemo": {
                                "waqfSegmentWords": ws,
                                "ibtidaSegmentWords": ib,
                                "waqfDemo": dm.get("waqfDemo"),
                                "ibtidaDemo": dm.get("ibtidaDemo"),
                            },
                            "prevAyahWords": compact_words(prev_words[-15:]) if prev_words else "",
                            "curAyahWords": compact_words(cur_words),
                            "nextAyahWords": compact_words(next_words[:15]) if next_words else "",
                        }
                        # Note if previous ayah ends with a stop record
                        if prev_words:
                            prev_end_id = f"s{s_num}-a{ay - 1}-w{prev_words[-1]['index']}"
                            if prev_end_id in stops_by_id:
                                cand["prevAyahEndVerdicts"] = [
                                    {"scholar": o["scholar"], "verdict": o["verdict"]}
                                    for o in stops_by_id[prev_end_id].get("opinions", [])
                                ]
                        candidates.append(cand)

    candidates.sort(key=lambda c: (-c["score"], c["surah"], c["ayah"], c["wordIndex"]))
    stats["totalCandidateDemos"] = len(candidates)
    stats["uniqueCandidateStops"] = len({c["stopId"] for c in candidates})
    return {"stats": stats, "candidates": candidates}


def _validate_coord(
    ayah_words: dict[int, int], ayah: int, word: int, label: str
) -> None:
    mw = ayah_words.get(ayah)
    if mw is None or word < 1 or word > mw:
        raise ValueError(f"{label}: invalid coordinate ({ayah}, {word}), maxWord={mw}")


def apply_patches(patches: list[dict[str, Any]], dry_run: bool = False) -> tuple[int, int]:
    """Validate and apply cross-ayah demo patches directly to app_feed JSON files."""
    by_surah: dict[int, list[dict[str, Any]]] = {}
    for p in patches:
        by_surah.setdefault(int(p["surah"]), []).append(p)

    files_updated = 0
    demos_updated = 0

    for s_num, s_patches in sorted(by_surah.items()):
        feed_path = APP_FEED_DIR / f"surah_{s_num:03d}.json"
        if not feed_path.exists():
            raise FileNotFoundError(f"Missing feed file: {feed_path}")
        data = json.loads(feed_path.read_text(encoding="utf-8"))
        ayah_lens = {int(a["number"]): len(a.get("words") or []) for a in data.get("ayahs", [])}
        stops_by_id = {s["id"]: s for s in data.get("stops", [])}

        changed = False
        for p in s_patches:
            stop = stops_by_id.get(p["stopId"])
            if stop is None:
                raise KeyError(f"Stop {p['stopId']} not found in surah_{s_num:03d}.json")
            ay = int(stop["ayah"])
            scholar = p["scholar"]
            op = next((o for o in stop.get("opinions", []) if o["scholar"] == scholar), None)
            if op is None:
                raise KeyError(f"Scholar {scholar!r} not found on {stop['id']}")
            demos = op.get("demosAndMeanings") or []
            target_verdict = p.get("verdict")
            target_qila = p.get("isQila")
            target_idx = p.get("demoIndex")

            matched_any = False
            for idx_d, dm in enumerate(demos):
                if target_idx is not None and idx_d != int(target_idx):
                    continue
                if target_verdict is not None and dm.get("verdict") != target_verdict:
                    continue
                if target_qila is not None and bool(dm.get("isQila", False)) != bool(target_qila):
                    continue

                if "waqfSegmentWords" in p and p["waqfSegmentWords"] is not None:
                    ws = p["waqfSegmentWords"]
                    w_sa = int(p.get("waqfStartAyah") or ay)
                    w_ea = int(p.get("waqfEndAyah") or ay)
                    _validate_coord(ayah_lens, w_sa, int(ws[0]), f"{stop['id']} waqf start")
                    _validate_coord(ayah_lens, w_ea, int(ws[1]), f"{stop['id']} waqf end")
                    if (w_sa, int(ws[0])) > (w_ea, int(ws[1])):
                        raise ValueError(f"{stop['id']}: reversed waqf span ({w_sa},{ws[0]})..({w_ea},{ws[1]})")
                    dm["waqfSegmentWords"] = [int(ws[0]), int(ws[1])]
                    if w_sa != ay:
                        dm["waqfStartAyah"] = w_sa
                    else:
                        dm.pop("waqfStartAyah", None)
                    if w_ea != ay:
                        dm["waqfEndAyah"] = w_ea
                    else:
                        dm.pop("waqfEndAyah", None)

                if "waqfDemo" in p and p["waqfDemo"]:
                    dm["waqfDemo"] = str(p["waqfDemo"]).strip()

                if "ibtidaSegmentWords" in p:
                    ib = p["ibtidaSegmentWords"]
                    if ib is None:
                        dm["ibtidaSegmentWords"] = None
                        dm.pop("ibtidaStartAyah", None)
                        dm.pop("ibtidaEndAyah", None)
                    else:
                        ib_sa = int(p.get("ibtidaStartAyah") or ay)
                        ib_ea = int(p.get("ibtidaEndAyah") or ib_sa)
                        _validate_coord(ayah_lens, ib_sa, int(ib[0]), f"{stop['id']} ibtida start")
                        _validate_coord(ayah_lens, ib_ea, int(ib[1]), f"{stop['id']} ibtida end")
                        if (ib_sa, int(ib[0])) > (ib_ea, int(ib[1])):
                            raise ValueError(f"{stop['id']}: reversed ibtida span ({ib_sa},{ib[0]})..({ib_ea},{ib[1]})")
                        dm["ibtidaSegmentWords"] = [int(ib[0]), int(ib[1])]
                        if ib_sa != ay:
                            dm["ibtidaStartAyah"] = ib_sa
                        else:
                            dm.pop("ibtidaStartAyah", None)
                        if ib_ea != ay:
                            dm["ibtidaEndAyah"] = ib_ea
                        else:
                            dm.pop("ibtidaEndAyah", None)

                if "ibtidaDemo" in p and p["ibtidaDemo"]:
                    dm["ibtidaDemo"] = str(p["ibtidaDemo"]).strip()

                matched_any = True
                demos_updated += 1
                changed = True

            if not matched_any:
                raise ValueError(
                    f"No matching demo for {stop['id']} scholar={scholar!r} verdict={target_verdict!r} isQila={target_qila!r}"
                )

        if changed and not dry_run:
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            feed_path.write_text(payload, encoding="utf-8")
            build_copy = BUILD_FEED_DIR / f"surah_{s_num:03d}.json"
            if build_copy.parent.exists():
                build_copy.write_text(payload, encoding="utf-8")
            files_updated += 1

    return files_updated, demos_updated


_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_TRAILING_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670\u06D6-\u06ED]+$")
_QIF_RE = re.compile(r"\[قف على:[^\]]+\]")


def _to_ar_num(n: int) -> str:
    return str(n).translate(_AR_DIGITS)


def _format_qif_word(word_text: str) -> str:
    """Turn final word of a span into a pausal [قف على: ...] label."""
    w = re.sub(r"[\u06D6-\u06ED]+", "", word_text or "").strip()
    if w.endswith(("ً", "ٍ", "ٌ", "َ", "ِ", "ُ")):
        w = _TRAILING_DIACRITICS_RE.sub("", w)
        if w.endswith("ة"):
            w = w[:-1] + "ةْ"
        elif not w.endswith(("ا", "ى", "و", "ي", "ْ", "آ")):
            w += "ْ"
    return w


def build_demo_text(
    ayah_words: dict[int, list[dict[str, Any]]],
    start_ay: int,
    start_w: int,
    end_ay: int,
    end_w: int,
    *,
    is_waqf: bool,
    existing_demo: str,
    cur_ay: int,
    cur_end_w: int,
) -> str:
    """Deterministically build waqfDemo / ibtidaDemo from verified app_feed words."""
    parts: list[str] = []
    last_word = ""
    for ay in range(start_ay, end_ay + 1):
        words = ayah_words[ay]
        lo = start_w if ay == start_ay else 1
        hi = end_w if ay == end_ay else len(words)
        seg = [w["text"] for w in words[lo - 1 : hi]]
        parts.extend(seg)
        if seg:
            last_word = seg[-1]
        if ay < end_ay:
            parts.append(f"۝{_to_ar_num(ay)}")
    body = " ".join(parts)

    qif_m = _QIF_RE.search(existing_demo or "")
    if is_waqf:
        suffix = qif_m.group(0) if qif_m else f"[قف على: {_format_qif_word(last_word)}]"
        return f"تلاوة: ﴿ {body} ﴾ {suffix}"

    # Keep original [قف على: ...] if ending at same position as original ayah
    if qif_m and end_ay == cur_ay and end_w == cur_end_w:
        suffix = qif_m.group(0)
    else:
        suffix = f"[قف على: {_format_qif_word(last_word)}]"
    return f"﴿ {body} ﴾ {suffix}"


def parse_k_selector(k_val: Any, n_ops: int) -> list[int]:
    """Parse '*', '1', 1, '1,2', or [1, 2] into validated 0-based op indices."""
    if k_val is None or str(k_val).strip() == "*":
        return list(range(n_ops))
    raw = k_val if isinstance(k_val, list) else re.split(r"[,;\s]+", str(k_val).strip())
    out: list[int] = []
    for tok in raw:
        s = str(tok).strip()
        if not s:
            continue
        if s == "*":
            return list(range(n_ops))
        idx = int(s)
        if idx < 0 or idx >= n_ops:
            raise ValueError(f"k index {idx} out of range (n_ops={n_ops})")
        if idx not in out:
            out.append(idx)
    return out


def _load_feed_cache(
    surahs: set[int], app_feed_dir: Path = APP_FEED_DIR
) -> dict[int, dict[str, Any]]:
    cache: dict[int, dict[str, Any]] = {}
    for s in sorted(surahs):
        d = json.loads((app_feed_dir / f"surah_{s:03d}.json").read_text(encoding="utf-8"))
        ayah_words = {int(a["number"]): list(a.get("words") or []) for a in d.get("ayahs", [])}
        ayah_str = {ay: compact_words(ws) for ay, ws in ayah_words.items()}
        end_verdicts: dict[int, list[str]] = {}
        dm_lookup: dict[tuple[str, str, int], dict[str, Any]] = {}
        for st in d.get("stops", []):
            ay = int(st["ayah"])
            wi = int(st["wordIndex"])
            if bool(st.get("isVerseEnd")) or wi == len(ayah_words.get(ay, [])):
                vs = sorted({
                    v.strip()
                    for o in st.get("opinions", [])
                    for v in (o.get("verdict") or [])
                    if v.strip()
                })
                if vs:
                    end_verdicts[ay] = vs
            for o in st.get("opinions", []):
                for idx_d, dm in enumerate(o.get("demosAndMeanings") or []):
                    dm_lookup[(st["id"], o.get("scholar", ""), idx_d)] = dm
        cache[s] = {
            "ayahWords": ayah_words,
            "ayahStr": ayah_str,
            "endVerdicts": end_verdicts,
            "dmLookup": dm_lookup,
        }
    return cache


def group_candidates_by_stop(
    candidates: list[dict[str, Any]], min_score: int = 3
) -> list[list[dict[str, Any]]]:
    """Filter by score and group candidate rows by stopId in reading order."""
    filtered = [c for c in candidates if int(c["score"]) >= min_score]
    by_stop: dict[tuple[int, int, int, str], list[dict[str, Any]]] = {}
    for c in filtered:
        key = (int(c["surah"]), int(c["ayah"]), int(c["wordIndex"]), c["stopId"])
        by_stop.setdefault(key, []).append(c)
    groups = []
    for key in sorted(by_stop):
        ops = sorted(
            by_stop[key],
            key=lambda x: (-int(x["score"]), x["scholar"], int(x.get("demoIndex", 0))),
        )
        groups.append(ops)
    return groups


def build_compact_batch(
    stop_groups: list[list[dict[str, Any]]],
    feed_cache: dict[int, dict[str, Any]],
    k_groups_out: dict[str, list[list[int]]] | None = None,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Build deduplicated {ayahs, stops} payload plus stopId->ops map."""
    needed_ayahs: set[tuple[int, int]] = set()
    stops_payload: list[dict[str, Any]] = []
    stop_ops_map: dict[str, list[dict[str, Any]]] = {}

    for ops in stop_groups:
        c0 = ops[0]
        s = int(c0["surah"])
        ay = int(c0["ayah"])
        wi = int(c0["wordIndex"])
        sid = c0["stopId"]
        sc = feed_cache[s]
        alen = len(sc["ayahWords"][ay])
        is_end = wi == alen
        stop_ops_map[sid] = ops

        for off in (-1, 0, 1):
            if (ay + off) in sc["ayahStr"]:
                needed_ayahs.add((s, ay + off))

        compact_ops: list[dict[str, Any]] = []
        seen_sigs: dict[tuple[Any, ...], int] = {}
        k_groups: list[list[int]] = []

        for orig_idx, c in enumerate(ops):
            ed = c["existingDemo"]
            cmt = (c.get("comment") or "").strip()
            mc = ""
            if len(cmt) < 25:
                dm = sc["dmLookup"].get((sid, c["scholar"], int(c.get("demoIndex", 0))), {})
                mc = (dm.get("meaningIfConnected") or "").strip()

            sig = (
                tuple(ed["waqfSegmentWords"]) if isinstance(ed["waqfSegmentWords"], list) else ed["waqfSegmentWords"],
                tuple(ed["ibtidaSegmentWords"]) if isinstance(ed["ibtidaSegmentWords"], list) else ed["ibtidaSegmentWords"],
                cmt,
                mc,
            )
            if sig in seen_sigs:
                k_groups[seen_sigs[sig]].append(orig_idx)
                continue

            compact_idx = len(compact_ops)
            seen_sigs[sig] = compact_idx
            k_groups.append([orig_idx])
            op_obj: dict[str, Any] = {
                "k": str(compact_idx),
                "ws": ed["waqfSegmentWords"],
                "ib": ed["ibtidaSegmentWords"],
                "cmt": cmt,
            }
            if mc:
                op_obj["mConn"] = mc
            compact_ops.append(op_obj)

        if k_groups_out is not None:
            k_groups_out[sid] = k_groups

        stop_obj: dict[str, Any] = {
            "id": sid,
            "w": f"{s}:{ay}:{wi} {c0['stopWord']}",
            "ops": compact_ops,
        }
        pv = sc["endVerdicts"].get(ay - 1)
        if pv and set(pv) != {"تام"}:
            stop_obj["prevEnd"] = pv
        cv = sc["endVerdicts"].get(ay)
        if cv and not is_end and set(cv) != {"تام"}:
            stop_obj["curEnd"] = cv
        stops_payload.append(stop_obj)

    ayahs_map = {
        f"{s}:{a}": feed_cache[s]["ayahStr"][a] for s, a in sorted(needed_ayahs)
    }
    return {"ayahs": ayahs_map, "stops": stops_payload}, stop_ops_map


def build_cross_ayah_prompt(payload: dict[str, Any]) -> str:
    n_stops = len(payload["stops"])
    ayahs_json = json.dumps(payload["ayahs"], ensure_ascii=False, indent=2)
    stops_json = json.dumps(payload["stops"], ensure_ascii=False, separators=(",", ":"))
    return (
        "أنت خبير متمرس في علم الوقف والابتداء، والنحو القرآني، وتحقيق كتب أئمة الوقف الخمسة "
        "(السجاوندي، الداني، ابن الأنباري، الأشموني، النحاس).\n\n"
        f"المهمة: راجع نصوص الأئمة المرفقة ({n_stops} موضعًا في `stops`) مع جدول الكلمات القرآنية المرقّمة 1-based في `ayahs` أدناه.\n"
        "حدد **فقط** المواضع والآراء (`ops`) التي يمتد فيها نطاق الوقف (`waqf`) إلى الآية السابقة (`ayah - 1`) "
        "أو يمتد فيها نطاق الابتداء (`ibtida`) إلى الآية التالية (`ayah + 1`) استنادًا صريحًا إلى كلام الإمام في `cmt` (و`mConn`/`prevEnd`).\n\n"
        "مواصفات الإخراج (مصفوفة JSON واحدة فقط داخل كتلة كود ```json):\n"
        "- أدرج فقط المواضع التي تحتاج تمديدًا عابرًا للآيات (أو أخرج `[]` إذا كانت كل المواضع ضمن نفس الآية).\n"
        "- صيغة كل عنصر:\n"
        "  - `id`: معرّف الموضع (`stopId`).\n"
        "  - `k`: `\"*\"` لجميع `ops` في هذا الموضع، أو رقم مفرد مثل `\"1\"`، أو أرقام مفصولة بفاصلة مثل `\"0,2\"`.\n"
        "  - `w`: `[startAyah, startWord, endAyah, endWord]` للوقف، أو `null` إذا بقي الوقف ضمن نفس الآية.\n"
        "  - `i`: `[startAyah, startWord, endAyah, endWord]` للابتداء، أو `null` إذا بقي الابتداء ضمن نفس الآية أو عند رأس الآية المعتاد.\n\n"
        "مثال مختصر للإخراج:\n"
        "```json\n"
        "[\n"
        '  {"id": "s104-a4-w1", "k": "*", "w": [3, 1, 4, 1], "i": null},\n'
        '  {"id": "s47-a20-w26", "k": "0,2", "w": null, "i": [20, 27, 21, 3]}\n'
        "]\n"
        "```\n\n"
        "مرجع أرقام الكلمات الدقيقة (`ayahs` 1-based):\n"
        f"```json\n{ayahs_json}\n```\n\n"
        f"قائمة المواضع المطلوب مراجعتها ({n_stops}):\n"
        f"```json\n{stops_json}\n```\n"
    )


def expand_compact_results(
    llm_items: list[dict[str, Any]],
    stop_ops_map: dict[str, list[dict[str, Any]]],
    feed_cache: dict[int, dict[str, Any]],
    stop_k_groups: dict[str, list[list[int]]] | None = None,
) -> list[dict[str, Any]]:
    """Expand sparse coordinate outputs into full validated app_feed patches."""
    patches: list[dict[str, Any]] = []
    for item in llm_items:
        sid = item.get("id")
        if sid not in stop_ops_map:
            raise KeyError(f"Unknown stopId returned by LLM: {sid!r}")
        ops = stop_ops_map[sid]
        kg = stop_k_groups.get(sid) if stop_k_groups else None
        n_compact = len(kg) if kg is not None else len(ops)
        compact_indices = parse_k_selector(item.get("k"), n_compact)
        indices: list[int] = []
        for ci in compact_indices:
            orig_list = kg[ci] if kg is not None else [ci]
            for oi in orig_list:
                if oi not in indices:
                    indices.append(oi)
        w_coords = item.get("w")
        i_coords = item.get("i")
        if w_coords is None and i_coords is None:
            continue

        for idx in indices:
            c = ops[idx]
            s = int(c["surah"])
            ay = int(c["ayah"])
            sc = feed_cache[s]
            ayah_words = sc["ayahWords"]
            ayah_lens = {a: len(ws) for a, ws in ayah_words.items()}
            dm = sc["dmLookup"].get((sid, c["scholar"], int(c.get("demoIndex", 0))), {})
            cur_end_w = len(ayah_words[ay])
            if isinstance(c["existingDemo"].get("ibtidaSegmentWords"), list):
                cur_end_w = int(c["existingDemo"]["ibtidaSegmentWords"][1])

            patch: dict[str, Any] = {
                "surah": s,
                "stopId": sid,
                "scholar": c["scholar"],
                "verdict": c["verdict"],
                "isQila": bool(c.get("isQila", False)),
                "demoIndex": int(c.get("demoIndex", 0)),
            }
            if w_coords is not None:
                w_sa, w_sw, w_ea, w_ew = [int(v) for v in w_coords]
                _validate_coord(ayah_lens, w_sa, w_sw, f"{sid} waqf start")
                _validate_coord(ayah_lens, w_ea, w_ew, f"{sid} waqf end")
                if (w_sa, w_sw) > (w_ea, w_ew):
                    raise ValueError(f"{sid}: reversed waqf ({w_sa},{w_sw})..({w_ea},{w_ew})")
                patch["waqfStartAyah"] = w_sa
                patch["waqfEndAyah"] = w_ea
                patch["waqfSegmentWords"] = [w_sw, w_ew]
                patch["waqfDemo"] = build_demo_text(
                    ayah_words, w_sa, w_sw, w_ea, w_ew,
                    is_waqf=True,
                    existing_demo=dm.get("waqfDemo") or "",
                    cur_ay=ay,
                    cur_end_w=cur_end_w,
                )
            if i_coords is not None:
                i_sa, i_sw, i_ea, i_ew = [int(v) for v in i_coords]
                _validate_coord(ayah_lens, i_sa, i_sw, f"{sid} ibtida start")
                _validate_coord(ayah_lens, i_ea, i_ew, f"{sid} ibtida end")
                if (i_sa, i_sw) > (i_ea, i_ew):
                    raise ValueError(f"{sid}: reversed ibtida ({i_sa},{i_sw})..({i_ea},{i_ew})")
                patch["ibtidaStartAyah"] = i_sa
                patch["ibtidaEndAyah"] = i_ea
                patch["ibtidaSegmentWords"] = [i_sw, i_ew]
                patch["ibtidaDemo"] = build_demo_text(
                    ayah_words, i_sa, i_sw, i_ea, i_ew,
                    is_waqf=False,
                    existing_demo=dm.get("ibtidaDemo") or "",
                    cur_ay=ay,
                    cur_end_w=cur_end_w,
                )
            patches.append(patch)
    return patches


async def run_batches(
    batch_size: int = 30,
    limit: int = 0,
    min_score: int = 3,
    dry_run: bool = False,
    no_apply: bool = False,
    out_patches: Path | None = None,
    backend: str = "gemini-web",
    profiles: list[str] | None = None,
    model: str = "gemini-4-argon",
    thinking_level: str = "high",
) -> None:
    if not CANDIDATES_OUT.exists():
        result = scan_candidates()
        CANDIDATES_OUT.parent.mkdir(parents=True, exist_ok=True)
        CANDIDATES_OUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        result = json.loads(CANDIDATES_OUT.read_text(encoding="utf-8"))

    done_keys: set[tuple[int, str, str, int]] = set()
    if CHECKPOINT_OUT.exists():
        for line in CHECKPOINT_OUT.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            done_keys.add((
                int(obj["surah"]),
                obj["stopId"],
                obj["scholar"],
                int(obj.get("demoIndex", 0)),
            ))

    pending = [
        c
        for c in result["candidates"]
        if (
            int(c["surah"]),
            c["stopId"],
            c["scholar"],
            int(c.get("demoIndex", 0)),
        )
        not in done_keys
    ]
    stop_groups = group_candidates_by_stop(pending, min_score=min_score)
    if limit > 0:
        stop_groups = stop_groups[:limit]
    if not stop_groups:
        print(f"All candidates with score >= {min_score} already processed in checkpoint.")
        return

    feed_cache = _load_feed_cache({int(ops[0]["surah"]) for ops in stop_groups})
    n_batches = (len(stop_groups) + batch_size - 1) // batch_size
    print(
        f"Prepared {len(stop_groups)} stops ({sum(len(g) for g in stop_groups)} demo rows) "
        f"with score >= {min_score} in {n_batches} compact batch(es) of {batch_size} stops."
    )

    if dry_run:
        sample_payload, _ = build_compact_batch(stop_groups[:batch_size], feed_cache)
        sample_prompt = build_cross_ayah_prompt(sample_payload)
        print(f"[DRY RUN] Batch 1 prompt chars={len(sample_prompt):,}, ayahs={len(sample_payload['ayahs'])}, stops={len(sample_payload['stops'])}")
        return

    if str(SCRATCH) not in sys.path:
        sys.path.insert(0, str(SCRATCH))
    if str(ROOT / "tools" / "gemini_parallel") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools" / "gemini_parallel"))
    import waqf_batch_utils as u  # noqa: E402
    from gemini_web_mcp_cli.core.exceptions import (  # noqa: E402
        APIError,
        GeminiReplyError,
        UsageLimitExceeded,
    )

    patches: list[dict[str, Any]] = []
    cb = None
    web_clients: dict[str, Any] = {}
    prof_list = profiles or ["niyyah"]
    ckpt_lock = asyncio.Lock()

    def _flush_out_patches() -> None:
        if out_patches is None:
            return
        all_ckpt_patches: dict[tuple[str, str, int], dict[str, Any]] = {}
        if CHECKPOINT_OUT.exists():
            for line in CHECKPOINT_OUT.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                if obj.get("waqfSegmentWords") or obj.get("ibtidaSegmentWords"):
                    k = (obj["stopId"], obj["scholar"], int(obj.get("demoIndex", 0)))
                    all_ckpt_patches[k] = obj
        for p in patches:
            all_ckpt_patches[(p["stopId"], p["scholar"], int(p.get("demoIndex", 0)))] = p
        merged = list(all_ckpt_patches.values())
        out_patches.parent.mkdir(parents=True, exist_ok=True)
        out_patches.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        if backend == "coarena":
            import coarena_backend as cb_mod  # noqa: E402
            cb = cb_mod
            cb.load_keys()
            worker_profs = ["coarena"]
        else:
            from gemini_web_mcp_cli.core.client import GeminiClient  # noqa: E402
            from gemini_web_mcp_cli.services.chat import ChatService  # noqa: E402
            worker_profs = []
            for p_name in prof_list:
                try:
                    c_obj = GeminiClient(profile_name=p_name, timeout=300.0)
                    await c_obj.init()
                    web_clients[p_name] = c_obj
                    worker_profs.append(p_name)
                except Exception as init_exc:
                    print(f"[CrossAyah INIT WARN] skipping profile {p_name!r}: {init_exc}")
            if not worker_profs:
                raise RuntimeError("No usable gemini-web profiles could be initialized.")

        def _is_transient_reply(text: str) -> bool:
            t = (text or "").strip().lower()
            if not t or len(t) > 400:
                return False
            markers = (
                "يفوق قدراتي",
                "لستُ مبرمجًا",
                "لست مبرمجا",
                "لستُ مصمّمًا",
                "لست مصمما",
                "ذكاء اصطناعي مستند إلى النصوص",
                "مجرّد نموذج لغوي",
                "مجرد نموذج لغوي",
                "لا يمكنني مساعدتك",
                "encountered an error",
                "hard time fulfilling",
                "something went wrong",
                "couldn't process",
                "try again",
            )
            return any(m in t for m in markers)

        work_q: asyncio.Queue[tuple[list[list[dict[str, Any]]], str, int]] = asyncio.Queue()
        chunks = [stop_groups[i : i + batch_size] for i in range(0, len(stop_groups), batch_size)]
        for b_idx, ch in enumerate(chunks):
            work_q.put_nowait((ch, f"{b_idx + 1}/{n_batches}", 0))

        consec_errors: dict[str, int] = {p: 0 for p in worker_profs}
        alive_workers = len(worker_profs)
        in_flight = 0
        max_retries = 5

        async def _worker(prof: str) -> None:
            nonlocal alive_workers, in_flight
            while True:
                if work_q.empty():
                    if in_flight == 0 or alive_workers <= 0:
                        return
                    await asyncio.sleep(0.5)
                    continue
                try:
                    chunk_groups, tag, attempt = work_q.get_nowait()
                except asyncio.QueueEmpty:
                    continue

                in_flight += 1
                retired = False
                should_sleep = False
                try:
                    k_groups_out: dict[str, list[list[int]]] = {}
                    payload, stop_ops_map = build_compact_batch(
                        chunk_groups, feed_cache, k_groups_out=k_groups_out
                    )
                    prompt = build_cross_ayah_prompt(payload)

                    try:
                        if backend == "coarena":
                            print(f"[CrossAyah {tag}] (coarena) sending {len(chunk_groups)} stops ({len(prompt):,} chars)...")
                            resp = await asyncio.wait_for(cb.CoarenaChatService().send(prompt), timeout=240.0)
                        else:
                            print(
                                f"[CrossAyah {tag}] (gemini-web:{prof} {model} {thinking_level}) "
                                f"sending {len(chunk_groups)} stops ({len(prompt):,} chars)..."
                            )
                            resp = await asyncio.wait_for(
                                ChatService(web_clients[prof]).send(
                                    prompt, model=model, thinking_level=thinking_level
                                ),
                                timeout=240.0,
                            )
                    except UsageLimitExceeded as exc:
                        print(f"[CrossAyah {prof}] quota limit reached: {exc}; re-queueing {tag} and retiring worker.")
                        work_q.put_nowait((chunk_groups, tag, attempt))
                        retired = True
                        break
                    except (APIError, GeminiReplyError, TimeoutError, asyncio.TimeoutError) as exc:
                        consec_errors[prof] += 1
                        err_s = str(exc)
                        if attempt < max_retries:
                            print(f"[CrossAyah {tag}] {type(exc).__name__} on {prof}: {err_s[:140]}; re-queueing attempt {attempt + 2}.")
                            work_q.put_nowait((chunk_groups, tag, attempt + 1))
                        else:
                            print(f"[CrossAyah {tag}] FAILED after {attempt + 1} attempts ({prof}): {err_s[:160]}")

                        if consec_errors[prof] >= 3 and alive_workers > 1:
                            print(f"[CrossAyah {prof}] retiring after {consec_errors[prof]} consecutive errors; other worker(s) will finish queue.")
                            retired = True
                            break
                        should_sleep = True
                        continue

                    raw_text = resp.text or ""
                    raw_file = SCRATCH / f"cross_ayah_raw_{tag.replace('/', '_of_')}.txt"
                    raw_file.parent.mkdir(parents=True, exist_ok=True)
                    raw_file.write_text(raw_text, encoding="utf-8")

                    if _is_transient_reply(raw_text):
                        if attempt < max_retries:
                            print(f"[CrossAyah {tag}] transient refusal on {prof}: {raw_text[:100]!r}; re-queueing attempt {attempt + 2}.")
                            work_q.put_nowait((chunk_groups, tag, attempt + 1))
                        else:
                            print(f"[CrossAyah {tag}] FAILED with refusal after {attempt + 1} attempts ({prof}).")
                        should_sleep = True
                        continue

                    try:
                        parsed = u.extract_json_value(raw_text)
                        if not isinstance(parsed, list):
                            raise ValueError(f"Expected JSON list, got {type(parsed)}")
                        batch_patches = expand_compact_results(
                            parsed, stop_ops_map, feed_cache, stop_k_groups=k_groups_out
                        )
                    except Exception as parse_exc:
                        print(f"[CrossAyah {tag}] PARSE/EXPAND ERROR on {prof} ({parse_exc}); raw -> {raw_file}")
                        if attempt < max_retries:
                            work_q.put_nowait((chunk_groups, tag, attempt + 1))
                        should_sleep = True
                        continue

                    consec_errors[prof] = 0
                    print(
                        f"[CrossAyah {tag}] ({prof}) "
                        f"LLM returned {len(parsed)} stop item(s) -> {len(batch_patches)} demo patch(es)."
                    )

                    patch_by_key = {
                        (p["stopId"], p["scholar"], int(p.get("demoIndex", 0))): p
                        for p in batch_patches
                    }
                    async with ckpt_lock:
                        patches.extend(batch_patches)
                        CHECKPOINT_OUT.parent.mkdir(parents=True, exist_ok=True)
                        with CHECKPOINT_OUT.open("a", encoding="utf-8") as fh:
                            for ops in chunk_groups:
                                for c in ops:
                                    k_tup = (c["stopId"], c["scholar"], int(c.get("demoIndex", 0)))
                                    p = patch_by_key.get(k_tup)
                                    rec = p if p else {
                                        "surah": int(c["surah"]),
                                        "stopId": c["stopId"],
                                        "scholar": c["scholar"],
                                        "verdict": c["verdict"],
                                        "isQila": bool(c.get("isQila", False)),
                                        "demoIndex": int(c.get("demoIndex", 0)),
                                        "needsCrossAyah": False,
                                    }
                                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        _flush_out_patches()
                        if batch_patches and not dry_run and not no_apply:
                            apply_patches(batch_patches, dry_run=False)
                finally:
                    in_flight -= 1
                    work_q.task_done()
                    if retired:
                        alive_workers = max(0, alive_workers - 1)

                if should_sleep:
                    await asyncio.sleep(3)

        await asyncio.gather(*(_worker(p) for p in worker_profs))
    finally:
        if cb is not None and hasattr(cb, "aclose"):
            await cb.aclose()
        for c_obj in web_clients.values():
            try:
                await c_obj.close()
            except Exception:
                pass

    _flush_out_patches()
    if out_patches is not None and out_patches.exists():
        merged_count = len(json.loads(out_patches.read_text(encoding="utf-8")))
        print(f"Saved {merged_count} expanded patch(es) -> {out_patches}")

    if patches:
        mode = "[NO-APPLY VALIDATED]" if (dry_run or no_apply) else "Applied live"
        if dry_run or no_apply:
            files_n, demos_n = apply_patches(patches, dry_run=True)
            print(f"{mode} {demos_n} cross-ayah demo patch(es) across {files_n} feed file(s).")
        else:
            print(f"{mode} {len(patches)} cross-ayah demo patch(es) across completed batches.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan & patch cross-ayah waqf/ibtida spans.")
    parser.add_argument("--scan", action="store_true", help="Scan app_feed for cross-ayah candidates.")
    parser.add_argument("--apply", type=str, help="Apply a JSON patch file to app_feed.")
    parser.add_argument("--dry-run", action="store_true", help="Validate patch or preview batch without writing files.")
    parser.add_argument("--run", "--run-coarena", dest="run_batches", action="store_true", help="Classify compact batches via LLM.")
    parser.add_argument("--backend", choices=["gemini-web", "coarena"], default="gemini-web", help="LLM backend (default: gemini-web).")
    parser.add_argument("--profiles", type=str, default="niyyah", help="Comma-separated gemini-web profiles (default: niyyah).")
    parser.add_argument("--model", type=str, default="gemini-4-argon", help="gemini-web model (default: gemini-4-argon).")
    parser.add_argument("--thinking", type=str, default="high", help="gemini-web thinking level (default: high).")
    parser.add_argument("--no-apply", action="store_true", help="Validate patches after LLM run without modifying app_feed.")
    parser.add_argument("--out-patches", type=str, help="Optional path to save expanded patches JSON.")
    parser.add_argument("--batch-size", type=int, default=30, help="Stops per compact batch (default 30).")
    parser.add_argument("--min-score", type=int, default=3, help="Minimum candidate score (default 3).")
    parser.add_argument("--limit", type=int, default=0, help="Max stops to process (0 = all).")
    args = parser.parse_args()

    if args.scan:
        result = scan_candidates()
        CANDIDATES_OUT.parent.mkdir(parents=True, exist_ok=True)
        CANDIDATES_OUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("Scan stats:", json.dumps(result["stats"], ensure_ascii=False))
        print(f"Saved {len(result['candidates'])} candidates -> {CANDIDATES_OUT}")

    if args.apply:
        patches = json.loads(Path(args.apply).read_text(encoding="utf-8"))
        files_n, demos_n = apply_patches(patches, dry_run=args.dry_run)
        prefix = "[DRY RUN] Validated" if args.dry_run else "Applied"
        print(f"{prefix} {demos_n} demo patch(es) across {files_n} feed file(s).")

    if args.run_batches:
        prof_list = [p.strip() for p in args.profiles.split(",") if p.strip()]
        asyncio.run(
            run_batches(
                batch_size=args.batch_size,
                limit=args.limit,
                min_score=args.min_score,
                dry_run=args.dry_run,
                no_apply=args.no_apply,
                out_patches=Path(args.out_patches) if args.out_patches else None,
                backend=args.backend,
                profiles=prof_list,
                model=args.model,
                thinking_level=args.thinking,
            )
        )


if __name__ == "__main__":
    main()
