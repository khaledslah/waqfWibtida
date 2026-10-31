"""
Scorecard comparison script for Surah Yusuf batches:
591_594, 595_598, 599_602, 603_606, 607_610.
Compares batch_TAG.apparatus_v4.raw.json (Grok / baseline)
vs batch_TAG.apparatus_v4_antigravity.raw.json (Antigravity re-extract).
"""
import json
import re
import sys
from pathlib import Path

OUT_DIR = Path("sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out")
TAGS = ["591_594", "595_598", "599_602", "603_606", "607_610"]


def clean_target(t):
    if not t:
        return ""
    t = re.sub(r"[﴿﴾\(\)\[\]]", "", t)
    t = re.sub(r"-\s*\d+\s*-[^\s]+", "", t)
    return t.strip()


def score_batch(tag):
    base_file = OUT_DIR / f"batch_{tag}.apparatus_v4.raw.json"
    side_file = OUT_DIR / f"batch_{tag}.apparatus_v4_antigravity.raw.json"

    if not side_file.exists():
        return {"tag": tag, "status": "PENDING"}

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
    only_base = set(base_map.keys()) - set(side_map.keys())
    only_side = set(side_map.keys()) - set(base_map.keys())

    label_delta = 0
    ref_delta = 0
    ops_base_total = sum(len(a.get("opinions", [])) for w in bw for a in w.get("apparatus", []))
    ops_side_total = sum(len(a.get("opinions", [])) for w in sw for a in w.get("apparatus", []))

    diff_details = []
    for k in sorted(shared_keys, key=lambda x: (x[0] or 0, x[1] or "")):
        b_item = base_map[k]
        s_item = side_map[k]
        diffs = []
        if b_item.get("verdict_label") != s_item.get("verdict_label"):
            label_delta += 1
            diffs.append(f"label: base='{b_item.get('verdict_label')}' vs side='{s_item.get('verdict_label')}'")
        if b_item.get("margin_ref") != s_item.get("margin_ref"):
            ref_delta += 1
            diffs.append(f"ref: base={b_item.get('margin_ref')} vs side={s_item.get('margin_ref')}")
        b_ops = sum(len(a.get("opinions", [])) for a in b_item.get("apparatus", []))
        s_ops = sum(len(a.get("opinions", [])) for a in s_item.get("apparatus", []))
        if b_ops != s_ops:
            diffs.append(f"ops: base={b_ops} vs side={s_ops}")
        if diffs:
            diff_details.append(f"Ayah {k[0]} [{k[1]}]: " + "; ".join(diffs))

    ops_delta = abs(ops_base_total - ops_side_total)

    status = "EXACT_MATCH" if (base_count == side_count and label_delta == 0 and ref_delta == 0 and ops_delta == 0 and not only_base and not only_side) else "PASS" if (abs(base_count - side_count) <= 1 and label_delta == 0) else "DIFF"

    return {
        "tag": tag,
        "base_count": base_count,
        "side_count": side_count,
        "shared_targets": len(shared_keys),
        "only_base": list(only_base),
        "only_side": list(only_side),
        "label_delta": label_delta,
        "ref_delta": ref_delta,
        "ops_base": ops_base_total,
        "ops_side": ops_side_total,
        "ops_delta": ops_delta,
        "diff_details": diff_details,
        "status": status,
    }


def main():
    print("=" * 95)
    print("SURAH YUSUF RE-EXTRACTION SCORECARD: GROK (BASE) vs ANTIGRAVITY (SIDE)")
    print("=" * 95)
    header = f"{'Tag':<10} | {'Base':<5} | {'Side':<5} | {'Shared':<6} | {'LabelΔ':<6} | {'RefΔ':<5} | {'Ops(B/S)':<10} | {'Status':<12}"
    print(header)
    print("-" * 95)

    tot_base = tot_side = tot_shared = tot_ld = tot_rd = tot_ob = tot_os = 0
    tot_ops_b = tot_ops_s = 0

    all_res = []
    for t in TAGS:
        r = score_batch(t)
        all_res.append(r)
        if r.get("status") == "PENDING":
            print(f"{t:<10} | {'--':<5} | {'--':<5} | {'--':<6} | {'--':<6} | {'--':<5} | {'--':<10} | {'PENDING':<12}")
            continue

        b = r.get("base_count", 0)
        s = r.get("side_count", 0)
        sh = r.get("shared_targets", 0)
        ld = r.get("label_delta", 0)
        rd = r.get("ref_delta", 0)
        op_b = r.get("ops_base", 0)
        op_s = r.get("ops_side", 0)

        tot_base += b
        tot_side += s
        tot_shared += sh
        tot_ld += ld
        tot_rd += rd
        tot_ops_b += op_b
        tot_ops_s += op_s

        ops_str = f"{op_b}/{op_s}"
        print(f"{t:<10} | {b:<5} | {s:<5} | {sh:<6} | {ld:<6} | {rd:<5} | {ops_str:<10} | {r.get('status',''):<12}")

    print("-" * 95)
    print(f"{'TOTAL':<10} | {tot_base:<5} | {tot_side:<5} | {tot_shared:<6} | {tot_ld:<6} | {tot_rd:<5} | {tot_ops_b}/{tot_ops_s:<7} |")
    print("=" * 95)

    for r in all_res:
        if r.get("diff_details") or r.get("only_base") or r.get("only_side"):
            print(f"\n--- Detailed Differences for Batch {r['tag']} ---")
            if r.get("only_base"):
                print("  Only in Base (Grok):", r["only_base"])
            if r.get("only_side"):
                print("  Only in Side (Antigravity):", r["only_side"])
            for d in r.get("diff_details", []):
                print(" ", d)


if __name__ == "__main__":
    main()
