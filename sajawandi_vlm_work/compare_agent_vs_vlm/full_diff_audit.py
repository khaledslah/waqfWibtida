import json
from pathlib import Path

OUT_DIR = Path("sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out")
TAGS = ["319_322", "311_314", "647_650", "347_350", "583_586", "475_478", "511_514", "211_214"]

for tag in TAGS:
    base = json.load(open(OUT_DIR / f"batch_{tag}.apparatus_v4.raw.json", encoding="utf-8-sig"))["waqfs"]
    side = json.load(open(OUT_DIR / f"batch_{tag}.apparatus_v4_antigravity.raw.json", encoding="utf-8-sig"))["waqfs"]
    diffs = []
    for i in range(max(len(base), len(side))):
        b = base[i] if i < len(base) else {}
        s = side[i] if i < len(side) else {}
        b_key = (b.get("ayah"), b.get("target_word"), b.get("verdict_label"), b.get("margin_ref"))
        s_key = (s.get("ayah"), s.get("target_word"), s.get("verdict_label"), s.get("margin_ref"))
        if b_key != s_key:
            diffs.append((i, b_key, s_key))
    print(f"=== {tag}: {len(diffs)} diffs out of {len(base)} ===")
    for d in diffs:
        print(f"  [{d[0]}] BASE: {d[1]}  vs  ANTIGRAVITY: {d[2]}")
