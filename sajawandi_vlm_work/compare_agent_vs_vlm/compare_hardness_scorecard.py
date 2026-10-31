"""
Scorecard comparison script for hardness test batches.
Compares batch_TAG.apparatus_v4.raw.json vs batch_TAG.apparatus_v4_antigravity.raw.json
"""
import json
import sys
from pathlib import Path

OUT_DIR = Path("sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out")
TAGS = ["319_322", "311_314", "647_650", "347_350", "583_586", "475_478", "511_514", "211_214"]


def clean_target(t):
    if not t:
        return ""
    # strip brackets, dashes, numbers, letters
    import re
    t = re.sub(r"[﴿﴾\(\)\[\]]", "", t)
    t = re.sub(r"-\s*\d+\s*-[^\s]+", "", t)
    return t.strip()


def score_batch(tag):
    base_file = OUT_DIR / f"batch_{tag}.apparatus_v4.raw.json"
    side_file = OUT_DIR / f"batch_{tag}.apparatus_v4_antigravity.raw.json"

    if not side_file.exists():
        return {"tag": tag, "status": "MISSING_OUTPUT"}

    try:
        base = json.load(open(base_file, encoding="utf-8-sig"))
        side = json.load(open(side_file, encoding="utf-8-sig"))
    except Exception as ex:
        return {"tag": tag, "status": f"JSON_ERROR: {ex}"}

    bw = base.get("waqfs", [])
    sw = side.get("waqfs", [])

    base_count = len(bw)
    side_count = len(sw)

    # Key by (ayah, clean_target)
    base_map = {}
    for w in bw:
        k = (w.get("ayah"), clean_target(w.get("target_word")))
        base_map[k] = w

    side_map = {}
    for w in sw:
        k = (w.get("ayah"), clean_target(w.get("target_word")))
        side_map[k] = w

    shared_keys = set(base_map.keys()) & set(side_map.keys())
    shared_targets = len(shared_keys)

    label_delta = 0
    ref_delta = 0
    ops_base_total = sum(len(a.get("opinions", [])) for w in bw for a in w.get("apparatus", []))
    ops_side_total = sum(len(a.get("opinions", [])) for w in sw for a in w.get("apparatus", []))

    for k in shared_keys:
        b_item = base_map[k]
        s_item = side_map[k]
        if b_item.get("verdict_label") != s_item.get("verdict_label"):
            label_delta += 1
        if b_item.get("margin_ref") != s_item.get("margin_ref"):
            ref_delta += 1

    ops_delta = abs(ops_base_total - ops_side_total)

    res = {
        "tag": tag,
        "base_count": base_count,
        "side_count": side_count,
        "shared_targets": shared_targets,
        "label_delta": label_delta,
        "ref_delta": ref_delta,
        "ops_base": ops_base_total,
        "ops_side": ops_side_total,
        "ops_delta": ops_delta,
        "status": "PASS" if (abs(base_count - side_count) <= 1 and label_delta == 0 and ref_delta == 0) else "WARN"
    }

    if tag == "211_214":
        # Special fail check on 211_214:
        # if الجنة is split wrong (ref null / empty apparatus) or a separate كذلك is invented vs the main file — report FAIL.
        jannah_found = False
        kazalika_invented = False
        for w in sw:
            tw = w.get("target_word", "")
            if "جنة" in tw or "الجنة" in tw:
                jannah_found = True
                if w.get("margin_ref") is None:
                    res["special_check"] = "FAIL: الجنة margin_ref is null"
                    res["status"] = "FAIL"
                elif not w.get("apparatus") or len(w["apparatus"]) == 0:
                    res["special_check"] = "FAIL: الجنة apparatus is empty"
                    res["status"] = "FAIL"
                else:
                    res["special_check"] = "PASS: الجنة has margin_ref and apparatus"
            if clean_target(tw) == "كذلك":
                kazalika_invented = True

        if not jannah_found:
            res["special_check"] = "FAIL: الجنة not found"
            res["status"] = "FAIL"
        elif kazalika_invented:
            res["special_check"] = "FAIL: separate كذلك was invented as a waqf"
            res["status"] = "FAIL"

    return res


def main():
    print(f"{'Tag':<10} | {'Base':<5} | {'Side':<5} | {'Shared':<6} | {'LabelΔ':<6} | {'RefΔ':<5} | {'Ops(B/S)':<10} | {'Status':<10} | {'Notes'}")
    print("-" * 85)
    all_pass = True
    for t in TAGS:
        r = score_batch(t)
        if r.get("status") != "PASS":
            all_pass = False
        notes = r.get("special_check", "")
        if r.get("status") in ("MISSING_OUTPUT",):
            print(f"{t:<10} | {'--':<5} | {'--':<5} | {'--':<6} | {'--':<6} | {'--':<5} | {'--':<10} | {r['status']:<10} | {notes}")
        else:
            ops_str = f"{r.get('ops_base')}/{r.get('ops_side')}"
            print(f"{t:<10} | {r.get('base_count',0):<5} | {r.get('side_count',0):<5} | {r.get('shared_targets',0):<6} | {r.get('label_delta',0):<6} | {r.get('ref_delta',0):<5} | {ops_str:<10} | {r.get('status',''):<10} | {notes}")


if __name__ == "__main__":
    main()
