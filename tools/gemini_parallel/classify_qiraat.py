#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan, classify (via LLM batch or patch), and apply Qira'at metadata
(`qiraatBasis`, `qiraatNote`) onto app_feed scholar opinions.

Usage:
  python tools/gemini_parallel/classify_qiraat.py --scan
  python tools/gemini_parallel/classify_qiraat.py --apply data/llm_prototype/qiraat_patches.json
  python tools/gemini_parallel/classify_qiraat.py --run-coarena --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
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
CANDIDATES_OUT = ROOT / "data" / "llm_prototype" / "qiraat_candidates.json"
CHECKPOINT_OUT = ROOT / "data" / "llm_prototype" / "qiraat_results.jsonl"

VALID_QIRAAT_BASES = {"non_hafs_only", "varies_by_qiraat", "hafs_and_others"}

QIRAAT_CUE_RE = re.compile(
    r"قراءة|من قرأ|وقرأ|قرئ|يقرأ|تقرأ|بفتح|بكسر|بضم|تشديد|تخفيف|"
    r"على قراءة|القرّاء|القراء|قراءتين|قراءتان"
)


def scan_qiraat_candidates(app_feed_dir: Path = APP_FEED_DIR) -> dict[str, Any]:
    """Find scholar opinions mentioning Qira'at / alternate readings."""
    candidates: list[dict[str, Any]] = []
    stats = {"surahsScanned": 0, "stopsMatched": 0, "opinionsMatched": 0, "alreadyTagged": 0}

    for fpath in sorted(app_feed_dir.glob("surah_*.json")):
        data = json.loads(fpath.read_text(encoding="utf-8"))
        stats["surahsScanned"] += 1
        s_num = int(data["surah"] if isinstance(data["surah"], int) else data["surah"]["number"])
        ayah_texts = {
            int(a["number"]): " ".join(w["text"] for w in (a.get("words") or []))
            for a in data.get("ayahs", [])
        }
        for stop in data.get("stops", []):
            stop_hit = False
            for op in stop.get("opinions", []):
                if op.get("qiraatBasis"):
                    stats["alreadyTagged"] += 1
                    continue
                cmt = op.get("comment") or ""
                demo_txt = " ".join(
                    f"{dm.get('meaningAtWaqf', '')} {dm.get('meaningIfConnected', '')}"
                    for dm in (op.get("demosAndMeanings") or [])
                )
                if QIRAAT_CUE_RE.search(cmt) or QIRAAT_CUE_RE.search(demo_txt):
                    stop_hit = True
                    stats["opinionsMatched"] += 1
                    candidates.append(
                        {
                            "surah": s_num,
                            "stopId": stop["id"],
                            "ayah": int(stop["ayah"]),
                            "stopWord": stop["word"],
                            "scholar": op["scholar"],
                            "verdicts": op.get("verdict", []),
                            "isQila": op.get("isQila", []),
                            "comment": cmt,
                            "ayahText": ayah_texts.get(int(stop["ayah"]), ""),
                        }
                    )
            if stop_hit:
                stats["stopsMatched"] += 1

    return {"stats": stats, "candidates": candidates}


def apply_qiraat_patches(
    patches: list[dict[str, Any]], dry_run: bool = False
) -> tuple[int, int]:
    """Validate and apply qiraatBasis / qiraatNote patches directly to app_feed."""
    by_surah: dict[int, list[dict[str, Any]]] = {}
    for p in patches:
        by_surah.setdefault(int(p["surah"]), []).append(p)

    files_updated = 0
    ops_updated = 0

    for s_num, s_patches in sorted(by_surah.items()):
        feed_path = APP_FEED_DIR / f"surah_{s_num:03d}.json"
        if not feed_path.exists():
            raise FileNotFoundError(f"Missing feed file: {feed_path}")
        data = json.loads(feed_path.read_text(encoding="utf-8"))
        stops_by_id = {s["id"]: s for s in data.get("stops", [])}

        changed = False
        for p in s_patches:
            stop = stops_by_id.get(p["stopId"])
            if stop is None:
                raise KeyError(f"Stop {p['stopId']} not found in surah_{s_num:03d}.json")
            scholar = p["scholar"]
            op = next((o for o in stop.get("opinions", []) if o["scholar"] == scholar), None)
            if op is None:
                raise KeyError(f"Scholar {scholar!r} not found on {stop['id']}")

            qb = p.get("qiraatBasis")
            qn = p.get("qiraatNote")
            if qb is not None and qb not in VALID_QIRAAT_BASES:
                raise ValueError(f"Invalid qiraatBasis={qb!r} at {stop['id']} ({scholar})")

            if qb:
                op["qiraatBasis"] = qb
                if isinstance(qn, str) and qn.strip():
                    op["qiraatNote"] = qn.strip()
                else:
                    op.pop("qiraatNote", None)
                ops_updated += 1
                changed = True
            elif "qiraatBasis" in op or "qiraatNote" in op:
                op.pop("qiraatBasis", None)
                op.pop("qiraatNote", None)
                ops_updated += 1
                changed = True

        if changed and not dry_run:
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            feed_path.write_text(payload, encoding="utf-8")
            build_copy = BUILD_FEED_DIR / f"surah_{s_num:03d}.json"
            if build_copy.parent.exists():
                build_copy.write_text(payload, encoding="utf-8")
            files_updated += 1

    return files_updated, ops_updated


def build_qiraat_batch_prompt(chunk: list[dict[str, Any]]) -> str:
    compact = [
        {
            "surah": c["surah"],
            "stopId": c["stopId"],
            "stopWord": c["stopWord"],
            "scholar": c["scholar"],
            "verdicts": c["verdicts"],
            "isQila": c["isQila"],
            "comment": c["comment"],
        }
        for c in chunk
    ]
    return (
        "أنت محقق متخصص في علم الوقف والابتداء والقراءات القرآنية (مقارنة برواية حفص عن عاصم).\n"
        f"صنّف كل مدخل في القائمة التالية ({len(compact)} مدخل) من حيث اعتماد الوقف على اختلاف القراءات:\n"
        "- `qiraatBasis`: أحد القيم التالية فقط:\n"
        "  1. `\"non_hafs_only\"`: الوقف المذكور مبني على قراءة أخرى غير حفص ولا يثبت/لا يتطابق مع لفظ أو قراءة حفص.\n"
        "  2. `\"varies_by_qiraat\"`: يتغيّر حكم الوقف نفسه (مثل جائز مقابل لا يوقف أو تام مقابل لا يوقف) باختلاف القراءة (حفص مقابل غيره).\n"
        "  3. `\"hafs_and_others\"`: ذُكرت قراءة أخرى في التعليل استطرادًا، لكن موضع الوقف وحكمه ثابتان في حفص كما في القراءة الأخرى.\n"
        "  4. `null`: ليس اختلاف قراءة قرآنية أصلًا (مثل حديث عن القراء/العرب أو مجرد معنى لغوي غير قرائي).\n"
        "- `qiraatNote`: تلخيص عربي موجز (3–8 كلمات عند غير `null`، مثل `\"على قراءة نافع وابن كثير\"` أو `\"قراءة التخفيف مقابل التشديد\"`)، أو `null` إذا كان `qiraatBasis` يساوي `null`.\n\n"
        "أخرج مصفوفة JSON واحدة فقط داخل ```json تحوي لكل عنصر: "
        "`surah`, `stopId`, `scholar`, `qiraatBasis`, `qiraatNote`:\n"
        f"```json\n{json.dumps(compact, ensure_ascii=False, indent=2)}\n```\n"
    )


async def run_coarena_batches(batch_size: int = 35, limit: int = 0) -> None:
    if str(SCRATCH) not in sys.path:
        sys.path.insert(0, str(SCRATCH))
    if str(ROOT / "tools" / "gemini_parallel") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools" / "gemini_parallel"))
    import coarena_backend as cb  # noqa: E402
    import waqf_batch_utils as u  # noqa: E402
    from gemini_web_mcp_cli.core.exceptions import UsageLimitExceeded  # noqa: E402

    if not CANDIDATES_OUT.exists():
        result = scan_qiraat_candidates()
        CANDIDATES_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        result = json.loads(CANDIDATES_OUT.read_text(encoding="utf-8"))

    done_keys: set[tuple[int, str, str]] = set()
    if CHECKPOINT_OUT.exists():
        for line in CHECKPOINT_OUT.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            done_keys.add((int(obj["surah"]), obj["stopId"], obj["scholar"]))

    todo = [
        c
        for c in result["candidates"]
        if (int(c["surah"]), c["stopId"], c["scholar"]) not in done_keys
    ]
    if limit > 0:
        todo = todo[:limit]
    if not todo:
        print("All Qira'at candidates already classified in checkpoint.")
        return

    cb.load_keys()
    patches: list[dict[str, Any]] = []
    for i in range(0, len(todo), batch_size):
        chunk = todo[i : i + batch_size]
        prompt = build_qiraat_batch_prompt(chunk)
        print(f"[Qiraat batch {i // batch_size + 1}] sending {len(chunk)} items...")
        chat = cb.CoarenaChatService()
        try:
            resp = await chat.send(prompt)
        except UsageLimitExceeded as exc:
            print(f"Stopped early on quota limit: {exc}")
            break
        parsed = u.extract_json_value(resp.text)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected JSON list, got {type(parsed)}")
        with CHECKPOINT_OUT.open("a", encoding="utf-8") as fh:
            for item in parsed:
                qb = item.get("qiraatBasis")
                if qb in VALID_QIRAAT_BASES:
                    patches.append(item)
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    if patches:
        files_n, ops_n = apply_qiraat_patches(patches)
        print(f"Applied {ops_n} Qira'at patch(es) across {files_n} feed file(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan & classify Qira'at-based waqf opinions.")
    parser.add_argument("--scan", action="store_true", help="Scan app_feed for Qira'at cues.")
    parser.add_argument("--apply", type=str, help="Apply JSON Qira'at patch file.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-coarena", action="store_true", help="Classify candidates via coarena API.")
    parser.add_argument("--batch-size", type=int, default=35)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if args.scan:
        result = scan_qiraat_candidates()
        CANDIDATES_OUT.parent.mkdir(parents=True, exist_ok=True)
        CANDIDATES_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Qira'at scan stats:", json.dumps(result["stats"], ensure_ascii=False))
        print(f"Saved {len(result['candidates'])} candidates -> {CANDIDATES_OUT}")

    if args.apply:
        patches = json.loads(Path(args.apply).read_text(encoding="utf-8"))
        files_n, ops_n = apply_qiraat_patches(patches, dry_run=args.dry_run)
        prefix = "[DRY RUN] Validated" if args.dry_run else "Applied"
        print(f"{prefix} {ops_n} Qira'at patch(es) across {files_n} feed file(s).")

    if args.run_coarena:
        asyncio.run(run_coarena_batches(batch_size=args.batch_size, limit=args.limit))


if __name__ == "__main__":
    main()
