"""
Generate pure Uthmani Waqf word-by-word dataset (WITHOUT Sajawandi data).

Reads:
- quran-words.json (77,429 words)

Outputs:
- quran-words-uthmani-waqf.json (root)
- WaqfReader/app/src/main/assets/quran_words_uthmani_waqf.json (assets)

Fields per word:
- s, v, p, u, i
- clean_u: Uthmani text with pause mark glyph stripped
- has_uthmani_waqf: boolean
- uthmani_waqf: 'صلى' | 'قلى' | 'ج' | 'مـ' | 'لا' | '∴' | 'س' | null
- uthmani_waqf_name: 'الوصل أولى' | 'الوقف أولى' | 'جائز' | 'لازم' | 'ممنوع' | 'معانقة' | 'سكتة' | null
- uthmani_waqf_code: 'SALA' | 'QALA' | 'JEEM' | 'MEEM' | 'LA' | 'MUANAQAH' | 'SAKTAH' | null
- uthmani_waqf_char: Unicode char ('ۖ', 'ۗ', 'ۚ', 'ۘ', 'ۙ', 'ۛ', 'ۜ') | null
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAUSE_CHARS = {
    "\u06d6": ("صلى", "الوصل أولى", "SALA"),
    "\u06d7": ("قلى", "الوقف أولى", "QALA"),
    "\u06da": ("ج", "جائز", "JEEM"),
    "\u06d8": ("مـ", "لازم", "MEEM"),
    "\u06d9": ("لا", "ممنوع", "LA"),
    "\u06db": ("∴", "معانقة", "MUANAQAH"),
}

SAKTAH_LOCATIONS = {
    (18, 1, 11),  # عوجا (الكهف)
    (36, 52, 6),  # مرقدنا (يس)
    (69, 28, 4),  # ماليه (الحاقة)
    (75, 27, 2),  # من راق (القيامة)
    (83, 14, 2),  # بل ران (المطففين)
}


def main():
    print("[*] Loading quran-words.json...")
    words = json.load(open(ROOT / "quran-words.json", encoding="utf-8"))
    print(f"    Loaded {len(words)} words.")

    out_words = []
    stats = {}

    for w in words:
        s, v, p, u, imla = w["s"], w["v"], w["p"], w["u"], w.get("i", "")

        found_mark = None
        for ch, (mark, name, code) in PAUSE_CHARS.items():
            if ch in u:
                found_mark = (ch, mark, name, code)
                break

        if (s, v, p) in SAKTAH_LOCATIONS and found_mark is None:
            found_mark = ("\u06dc", "س", "سكتة", "SAKTAH")

        clean = u
        for ch in PAUSE_CHARS:
            clean = clean.replace(ch, "")
        if (s, v, p) in SAKTAH_LOCATIONS:
            clean = clean.replace("\u06dc", "")
        clean = clean.strip()

        has_waqf = found_mark is not None
        if has_waqf:
            stats[found_mark[1]] = stats.get(found_mark[1], 0) + 1

        entry = {
            "s": s,
            "v": v,
            "p": p,
            "u": u,
            "i": imla,
            "clean_u": clean,
            "has_uthmani_waqf": has_waqf,
            "uthmani_waqf": found_mark[1] if has_waqf else None,
            "uthmani_waqf_name": found_mark[2] if has_waqf else None,
            "uthmani_waqf_code": found_mark[3] if has_waqf else None,
            "uthmani_waqf_char": found_mark[0] if has_waqf else None,
        }
        out_words.append(entry)

    print("\n[+] Uthmani Waqf Counts:")
    for k, c in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"    {k}: {c:,}")
    print(f"    Total words with Uthmani waqfs: {sum(stats.values()):,} / {len(out_words):,}")

    out_root = ROOT / "quran-words-uthmani-waqf.json"
    with open(out_root, "w", encoding="utf-8") as f:
        json.dump(out_words, f, ensure_ascii=False, indent=1)
    print(f"\n[✓] Created {out_root} ({out_root.stat().st_size / (1024*1024):.2f} MB)")

    out_assets = ROOT / "WaqfReader/app/src/main/assets/quran_words_uthmani_waqf.json"
    out_assets.parent.mkdir(parents=True, exist_ok=True)
    with open(out_assets, "w", encoding="utf-8") as f:
        json.dump(out_words, f, ensure_ascii=False, indent=1)
    print(f"[✓] Created {out_assets} ({out_assets.stat().st_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    main()
