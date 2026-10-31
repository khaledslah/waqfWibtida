import json
from pathlib import Path

OUT_DIR = Path("sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out")

def inspect_diff(tag):
    base_p = OUT_DIR / f"batch_{tag}.apparatus_v4.raw.json"
    side_p = OUT_DIR / f"batch_{tag}.apparatus_v4_antigravity.raw.json"
    if not side_p.exists():
        print(f"{tag}: side missing")
        return
    base = json.load(open(base_p, encoding="utf-8-sig"))["waqfs"]
    side = json.load(open(side_p, encoding="utf-8-sig"))["waqfs"]
    print(f"\n=================== {tag} (Base: {len(base)}, Side: {len(side)}) ===================")
    for i in range(max(len(base), len(side))):
        b = base[i] if i < len(base) else {}
        s = side[i] if i < len(side) else {}
        b_summary = f"[{b.get('ayah')}] {b.get('target_word')} ({b.get('verdict_label')}) ref:{b.get('margin_ref')} p:{b.get('text_page')}"
        s_summary = f"[{s.get('ayah')}] {s.get('target_word')} ({s.get('verdict_label')}) ref:{s.get('margin_ref')} p:{s.get('text_page')}"
        diff_flag = " " if b_summary == s_summary else "*"
        print(f"{diff_flag} [{i:02d}] B: {b_summary}")
        if diff_flag == "*":
            print(f"      S: {s_summary}")

inspect_diff("211_214")
inspect_diff("311_314")
