"""
Build the WaqfReader Android mockup from REAL project data.

Inputs (read-only):
  - WaqfReader/app/src/main/assets/quran_words.json         (Uthmani words)
  - sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out/batch_*.apparatus_v4.raw.json

Output:
  - WaqfReader/mockup/waqf_reader_mockup.html  (self-contained; template + injected JSON)

Usage:
  python WaqfReader/mockup/build_mockup.py            # default: Al-Baqarah 136-140
  python WaqfReader/mockup/build_mockup.py 2 136 140 243_246 247_250
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WORDS = ROOT / "WaqfReader" / "app" / "src" / "main" / "assets" / "quran_words.json"
OUT_DIR = ROOT / "sajawandi_vlm_work" / "compare_agent_vs_vlm" / "_full_run" / "out"
TEMPLATE = HERE / "mockup_template.html"
OUTPUT = HERE / "waqf_reader_mockup.html"

SURAH_NAMES = {1: "الفاتحة", 2: "البقرة", 3: "آل عمران"}

# Diacritics, Quranic annotation marks, tatweel
_STRIP = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
# alif / hamza carriers are dropped entirely so Uthmani and imla'i spellings meet
_DROP = re.compile(r"[\u0621\u0622\u0623\u0625\u0627\u0671]")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def norm(s: str) -> str:
    s = _STRIP.sub("", s)
    s = _DROP.sub("", s)
    s = s.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    return [t for t in norm(s).split(" ") if t]


def main() -> None:
    args = sys.argv[1:]
    surah = int(args[0]) if args else 2
    a_from = int(args[1]) if len(args) > 1 else 136
    a_to = int(args[2]) if len(args) > 2 else 140
    tags = args[3:] or ["243_246", "247_250"]

    words = json.load(open(WORDS, encoding="utf-8"))

    # flattened page words (index = position on the mock page)
    page_words: list[dict] = []
    ayahs = []
    for a in range(a_from, a_to + 1):
        ws = words[f"{surah}:{a}"]
        first = len(page_words)
        for w in ws:
            page_words.append({"i": len(page_words), "ayah": a, "p": w["p"], "t": w["t"], "n": norm(w["t"])})
        ayahs.append({"n": a, "from": first, "to": len(page_words) - 1})

    def find_seq(toks: list[str], start: int, ayah: int | None = None) -> int | None:
        """Return page index of the LAST token of the first match at/after start."""
        k = len(toks)
        for i in range(start, len(page_words) - k + 1):
            if ayah is not None and page_words[i]["ayah"] != ayah:
                continue
            if all(page_words[i + j]["n"] == toks[j] for j in range(k)):
                return i + k - 1
        return None

    raw = []
    pages = []
    for tag in tags:
        p = OUT_DIR / f"batch_{tag}.apparatus_v4.raw.json"
        if not p.exists():
            print(f"[skip] {p.name} missing")
            continue
        d = json.load(open(p, encoding="utf-8-sig"))
        pages += d.get("page_numbers", [])
        raw += [w for w in d.get("waqfs", []) if a_from <= w["ayah"] <= a_to]

    waqfs = []
    cursor: dict[int, int] = {}
    unmapped = []
    for n, w in enumerate(raw):
        ay = w["ayah"]
        first_of_ayah = next(x["from"] for x in ayahs if x["n"] == ay)
        start = cursor.get(ay, first_of_ayah)
        idx = find_seq(tokens(w["target_word"]), start, ay)
        if idx is None:
            unmapped.append(w["target_word"])
            continue
        cursor[ay] = idx + 1

        app_out = []
        for a in w.get("apparatus", []):
            sug = a.get("suggested") or {}
            s_waqf, s_ibt = [], []
            for s in sug.get("waqf", []) or []:
                tt = tokens(s["target_word"])
                si = idx if tt == tokens(w["target_word"]) else find_seq(tt, 0)
                s_waqf.append({**s, "word": si})
            for s in sug.get("ibtida", []) or []:
                si = find_seq(tokens(s["start_word"])[:1], idx + 1)
                s_ibt.append({**s, "word": si})
            app_out.append({
                "margin_ref": a.get("margin_ref"),
                "text_page": a.get("text_page"),
                "raw_text": a.get("raw_text"),
                "continuation": a.get("continuation"),
                "opinions": a.get("opinions", []),
                "suggested": {"waqf": s_waqf, "ibtida": s_ibt} if (s_waqf or s_ibt) else None,
            })

        waqfs.append({
            "id": f"w{n}",
            "ayah": ay,
            "word": idx,
            "target": w["target_word"],
            "label": w.get("verdict_label"),
            "verdict": w.get("verdict"),
            "margin_ref": w.get("margin_ref"),
            "text": w.get("text"),
            "text_page": w.get("text_page"),
            "old_text": w.get("old_text"),
            "fixes": w.get("fixes", []),
            "apparatus": app_out,
        })

    data = {
        "surah": surah,
        "surahName": SURAH_NAMES.get(surah, str(surah)),
        "ayahFrom": a_from,
        "ayahTo": a_to,
        "bookPages": sorted({w["text_page"] for w in waqfs if w.get("text_page")}) or sorted(set(pages)),
        "words": [{"i": w["i"], "ayah": w["ayah"], "t": w["t"]} for w in page_words],
        "ayahs": ayahs,
        "waqfs": waqfs,
    }

    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    OUTPUT.write_text(tpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
    print(f"waqfs={len(waqfs)} unmapped={unmapped} words={len(page_words)} -> {OUTPUT}")


if __name__ == "__main__":
    main()
