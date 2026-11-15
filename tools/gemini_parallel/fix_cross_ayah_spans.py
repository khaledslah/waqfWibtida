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
    r"ما قبله|الآية السابق|الآيه السابق|رأس الآية قبله|وصلها بما قبل|"
    r"مرتبط بالسابق|تعلق\s+[^.،؛]*قبله|متعلق\s+[^.،؛]*قبل|صلة\s+لـ?"
)
FORWARD_CUE_RE = re.compile(
    r"الآية التالي|ما بعده|الآية بعد|يتصل بالآية|تعلق\s+[^.،؛]*بعده|"
    r"متعلق\s+[^.،؛]*بعد"
)


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
    stats = {
        "surahsScanned": 0,
        "backwardHighScore": 0,
        "forwardHighScore": 0,
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

            prev_words = ayah_words.get(ay - 1, [])
            next_words = ayah_words.get(ay + 1, [])

            # Distinctive tail words in Ayah N-1 not appearing in Ayah N
            cur_norm_set = {norm_ar(w["text"]) for w in cur_words}
            prev_tail = [
                (w["index"], norm_ar(w["text"]))
                for w in prev_words[-12:]
                if len(norm_ar(w["text"])) >= 4
                and norm_ar(w["text"]) not in STOPWORDS_AR
                and norm_ar(w["text"]) not in cur_norm_set
            ]
            next_head = [
                (w["index"], norm_ar(w["text"]))
                for w in next_words[:10]
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
                    mw_txt = f"{dm.get('meaningAtWaqf', '')} {dm.get('meaningIfConnected', '')}"
                    mi_txt = f"{dm.get('meaningAtIbtida', '')} {dm.get('meaningIfConnected', '')}"

                    reasons: list[str] = []
                    score = 0

                    # Backward waqf candidate (ws hits word 1 on ayah > 1)
                    if prev_words and isinstance(ws, list) and len(ws) >= 2 and ws[0] == 1:
                        matched_prev = [
                            (idx_w, txt_w)
                            for idx_w, txt_w in prev_tail
                            if re.search(
                                rf"(?:^|[^\u0621-\u064A])(?:و|ف|ب|ل)?{re.escape(txt_w)}(?:$|[^\u0621-\u064A])",
                                cmt_norm,
                            )
                        ]
                        if wi <= 6 and (matched_prev or BACKWARD_CUE_RE.search(cmt) or BACKWARD_CUE_RE.search(mw_txt)):
                            score += 3 if matched_prev else 2
                            reasons.append("early_in_ayah_backward_ref")
                        elif matched_prev and BACKWARD_CUE_RE.search(cmt):
                            score += 2
                            reasons.append("prev_word_and_cue")

                        if matched_prev:
                            reasons.append(
                                "cites_prev_words=" + ",".join(f"{i}:{w}" for i, w in matched_prev[:4])
                            )

                    # Forward ibtida candidate (stops whose ibtida runs to end and connects to N+1)
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
                        if not is_end and FORWARD_CUE_RE.search(cmt + " " + mi_txt):
                            score += 2 if matched_next else 1
                            reasons.append("mid_ayah_ibtida_reaches_end_with_cue")

                    if score >= 2:
                        if any("backward" in r or "prev_word" in r for r in reasons):
                            stats["backwardHighScore"] += 1
                        if any("ibtida" in r for r in reasons):
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

            matched_any = False
            for dm in demos:
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


def build_cross_ayah_prompt(chunk: list[dict[str, Any]]) -> str:
    compact = [
        {
            "surah": c["surah"],
            "stopId": c["stopId"],
            "ayah": c["ayah"],
            "stopWord": c["stopWord"],
            "scholar": c["scholar"],
            "verdict": c["verdict"],
            "isQila": c["isQila"],
            "comment": c["comment"],
            "existingDemo": c["existingDemo"],
            "prevAyahWords": c["prevAyahWords"],
            "curAyahWords": c["curAyahWords"],
            "nextAyahWords": c["nextAyahWords"],
        }
        for c in chunk
    ]
    return (
        "أنت محقق متخصص في علم الوقف والابتداء.\n"
        f"راجع كل مدخل في القائمة ({len(compact)} مدخل) وحدد إن كان `waqfSegmentWords` أو `ibtidaSegmentWords` "
        "يمتد فعلاً إلى الآية السابقة (`ayah - 1`) أو الآية التالية (`ayah + 1`) بناءً على تعليل العالم ونص الآيات.\n"
        "- إذا امتد إلى آية أخرى، أخرج: `surah`, `stopId`, `scholar`, `verdict`, `isQila`, "
        "`needsCrossAyah`: true, `waqfStartAyah`, `waqfEndAyah`, `waqfSegmentWords`, `waqfDemo`, "
        "`ibtidaStartAyah`, `ibtidaEndAyah`, `ibtidaSegmentWords`, `ibtidaDemo` "
        "(أدخل حدود `۝رقم_الآية` بين الآيتين داخل `waqfDemo` / `ibtidaDemo`).\n"
        "- إذا لم يحتج امتدادًا عابرًا للآيات، أخرج `needsCrossAyah`: false.\n"
        "أخرج مصفوفة JSON واحدة فقط داخل ```json:\n"
        f"```json\n{json.dumps(compact, ensure_ascii=False, indent=2)}\n```\n"
    )


async def run_coarena_batches(batch_size: int = 20, limit: int = 0) -> None:
    if str(SCRATCH) not in sys.path:
        sys.path.insert(0, str(SCRATCH))
    if str(ROOT / "tools" / "gemini_parallel") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools" / "gemini_parallel"))
    import coarena_backend as cb  # noqa: E402
    import waqf_batch_utils as u  # noqa: E402
    from gemini_web_mcp_cli.core.exceptions import UsageLimitExceeded  # noqa: E402

    if not CANDIDATES_OUT.exists():
        result = scan_candidates()
        CANDIDATES_OUT.parent.mkdir(parents=True, exist_ok=True)
        CANDIDATES_OUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        result = json.loads(CANDIDATES_OUT.read_text(encoding="utf-8"))

    done_keys: set[tuple[int, str, str, str, bool]] = set()
    if CHECKPOINT_OUT.exists():
        for line in CHECKPOINT_OUT.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            done_keys.add((
                int(obj["surah"]),
                obj["stopId"],
                obj["scholar"],
                str(obj.get("verdict") or ""),
                bool(obj.get("isQila", False)),
            ))

    todo = [
        c
        for c in result["candidates"]
        if (
            int(c["surah"]),
            c["stopId"],
            c["scholar"],
            str(c.get("verdict") or ""),
            bool(c.get("isQila", False)),
        )
        not in done_keys
    ]
    if limit > 0:
        todo = todo[:limit]
    if not todo:
        print("All cross-ayah candidates already processed in checkpoint.")
        return

    cb.load_keys()
    patches: list[dict[str, Any]] = []
    for i in range(0, len(todo), batch_size):
        chunk = todo[i : i + batch_size]
        prompt = build_cross_ayah_prompt(chunk)
        print(f"[CrossAyah batch {i // batch_size + 1}] sending {len(chunk)} items...")
        chat = cb.CoarenaChatService()
        try:
            resp = await chat.send(prompt)
        except UsageLimitExceeded as exc:
            print(f"Stopped early on quota limit: {exc}")
            break
        parsed = u.extract_json_value(resp.text)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected JSON list, got {type(parsed)}")
        CHECKPOINT_OUT.parent.mkdir(parents=True, exist_ok=True)
        with CHECKPOINT_OUT.open("a", encoding="utf-8") as fh:
            for item in parsed:
                if item.get("needsCrossAyah"):
                    patches.append(item)
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    if patches:
        files_n, demos_n = apply_patches(patches)
        print(f"Applied {demos_n} cross-ayah demo patch(es) across {files_n} feed file(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan & patch cross-ayah waqf/ibtida spans.")
    parser.add_argument("--scan", action="store_true", help="Scan app_feed for cross-ayah candidates.")
    parser.add_argument("--apply", type=str, help="Apply a JSON patch file to app_feed.")
    parser.add_argument("--dry-run", action="store_true", help="Validate patch without writing files.")
    parser.add_argument("--run-coarena", action="store_true", help="Classify candidates via coarena API.")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0)
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

    if args.run_coarena:
        asyncio.run(run_coarena_batches(batch_size=args.batch_size, limit=args.limit))


if __name__ == "__main__":
    main()
