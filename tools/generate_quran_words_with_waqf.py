"""
Generate an enriched quran-words-with-waqf.json dataset.

Reads:
- quran-words.json (77,429 words)
- sajawandi_surah_page_map.json
- sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out/batch_*.apparatus_v4.raw.json

Outputs:
- quran-words-with-waqf.json (root)
- WaqfReader/app/src/main/assets/quran_words_with_waqf.json (assets)

Each word contains:
- Original fields: s (surah), v (verse/ayah), p (word index in ayah), u (Uthmani text), i (Imla'i text)
- clean_u: Uthmani text stripped of pause mark glyphs
- has_uthmani_waqf: boolean
- uthmani_waqf: string label ('صلى', 'قلى', 'ج', 'مـ', 'لا', '∴', 'س') or null
- uthmani_waqf_name: Arabic rule name ('الوصل أولى', 'الوقف أولى', 'جائز', 'لازم', 'ممنوع', 'معانقة', 'سكتة') or null
- uthmani_waqf_code: canonical code ('SALA', 'QALA', 'JEEM', 'MEEM', 'LA', 'MUANAQAH', 'SAKTAH') or null
- uthmani_waqf_char: Unicode pause character or null
- sajawandi_waqf: Sajawandi apparatus verdict and details or null
"""

import glob
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Uthmani Pause Characters Mapping
PAUSE_CHARS = {
    "\u06d6": ("صلى", "الوصل أولى", "SALA"),
    "\u06d7": ("قلى", "الوقف أولى", "QALA"),
    "\u06da": ("ج", "جائز", "JEEM"),
    "\u06d8": ("مـ", "لازم", "MEEM"),
    "\u06d9": ("لا", "ممنوع", "LA"),
    "\u06db": ("∴", "معانقة", "MUANAQAH"),
}

# Specific Hafs Saktah locations (where \u06dc is a pause, not an internal pronunciation marker)
SAKTAH_LOCATIONS = {
    (18, 1, 11),  # عِوَجَا ۜ (الكهف)
    (36, 52, 6),  # مَّرْقَدِنَا ۜ (يس)
    (69, 28, 4),  # مَالِيَهْ ۜ (الحاقة)
    (75, 27, 2),  # مَنْ ۜ (القيامة)
    (83, 14, 2),  # بَلْ ۜ (المطففين)
}

# Normalization for matching
_STRIP = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_DROP = re.compile(r"[\u0621\u0622\u0623\u0625\u0627\u0671]")


def norm(text: str) -> str:
    if not text:
        return ""
    t = _STRIP.sub("", text)
    t = _DROP.sub("", t)
    t = t.replace("ة", "ه").replace("ى", "ي")
    return t.strip()


def clean_target(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"[﴿﴾\(\)\[\]]", "", t)
    t = re.sub(r"-\s*\d+\s*-[^\s]+", "", t)
    return t.strip()


def main():
    print("[*] Loading quran-words.json...")
    words = json.load(open(ROOT / "quran-words.json", encoding="utf-8"))
    print(f"    Loaded {len(words)} words.")

    print("[*] Loading sajawandi_surah_page_map.json...")
    surah_map = json.load(open(ROOT / "sajawandi_surah_page_map.json", encoding="utf-8"))["surahs"]

    def page_to_surahs(page):
        res = []
        for s_num, s_info in surah_map.items():
            if s_info["start"] <= page <= s_info["end"]:
                res.append(int(s_num))
        return res

    print("[*] Loading Sajawandi apparatus files (253 batches)...")
    batch_files = sorted(
        glob.glob(str(ROOT / "sajawandi_vlm_work/compare_agent_vs_vlm/_full_run/out/batch_*.apparatus_v4.raw.json"))
    )
    sajawandi_waqfs = []
    for bf in batch_files:
        d = json.load(open(bf, encoding="utf-8"))
        for w in d.get("waqfs", []):
            sajawandi_waqfs.append(w)
    print(f"    Loaded {len(sajawandi_waqfs)} Sajawandi waqfs.")

    # Index words by (s, v) -> list of (index, word, normalized_word)
    words_by_sv = defaultdict(list)
    for idx, w in enumerate(words):
        words_by_sv[(w["s"], w["v"])].append((idx, w, norm(w["u"])))

    # Map Sajawandi waqfs to words
    word_to_sajawandi = {}
    matched_sajawandi = 0

    for sw in sajawandi_waqfs:
        page = sw.get("text_page") or 0
        ayah = sw.get("ayah")
        if not ayah:
            continue
        surahs = page_to_surahs(page)
        target = clean_target(sw.get("target_word", ""))
        target_tokens = [norm(tok) for tok in target.split() if norm(tok)]
        if not target_tokens:
            continue

        matched_idx = None
        for s in surahs:
            sv_words = words_by_sv.get((s, ayah), [])
            if not sv_words:
                continue

            # Exact sequence match from end token
            last_tok = target_tokens[-1]
            for g_idx, word_obj, n_w in sv_words:
                if n_w == last_tok or (len(last_tok) >= 3 and (n_w.endswith(last_tok) or last_tok.endswith(n_w))):
                    matched_idx = g_idx
                    break
            if matched_idx is not None:
                break

        if matched_idx is not None:
            matched_sajawandi += 1
            opinions_count = sum(len(a.get("opinions", [])) for a in sw.get("apparatus", []))
            word_to_sajawandi[matched_idx] = {
                "label": sw.get("verdict_label"),
                "verdict": sw.get("verdict"),
                "target_word": sw.get("target_word"),
                "text_page": sw.get("text_page"),
                "margin_ref": sw.get("margin_ref"),
                "has_apparatus": len(sw.get("apparatus", [])) > 0,
                "apparatus_count": len(sw.get("apparatus", [])),
                "opinions_count": opinions_count,
            }

    print(f"    Sajawandi waqfs aligned to words: {matched_sajawandi} / {len(sajawandi_waqfs)} ({matched_sajawandi/len(sajawandi_waqfs)*100:.1f}%)")

    # Build enriched word entries
    print("[*] Enriching words with Uthmani waqfs and Sajawandi verdicts...")
    enriched_words = []
    uthmani_stats = defaultdict(int)

    for idx, w in enumerate(words):
        s, v, p, u, imla = w["s"], w["v"], w["p"], w["u"], w.get("i", "")

        # Detect Uthmani pause mark
        found_mark = None
        for ch, (mark, name, code) in PAUSE_CHARS.items():
            if ch in u:
                found_mark = (ch, mark, name, code)
                break

        # Check saktah
        if (s, v, p) in SAKTAH_LOCATIONS:
            if found_mark is None:
                found_mark = ("\u06dc", "س", "سكتة", "SAKTAH")

        # Clean text
        clean = u
        for ch in PAUSE_CHARS:
            clean = clean.replace(ch, "")
        if (s, v, p) in SAKTAH_LOCATIONS:
            clean = clean.replace("\u06dc", "")
        clean = clean.strip()

        has_waqf = found_mark is not None
        if has_waqf:
            uthmani_stats[found_mark[1]] += 1

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
            "sajawandi_waqf": word_to_sajawandi.get(idx),
        }
        enriched_words.append(entry)

    print("\n[+] Uthmani Waqf Distribution:")
    for k, count in sorted(uthmani_stats.items(), key=lambda x: -x[1]):
        print(f"    {k}: {count:,}")
    print(f"    Total words with Uthmani waqfs: {sum(uthmani_stats.values()):,} / {len(enriched_words):,}")

    # Write root file
    out_root = ROOT / "quran-words-with-waqf.json"
    print(f"\n[*] Writing {out_root}...")
    with open(out_root, "w", encoding="utf-8") as f:
        json.dump(enriched_words, f, ensure_ascii=False, indent=1)
    print(f"    File size: {out_root.stat().st_size / (1024*1024):.2f} MB")

    # Write assets file
    out_assets = ROOT / "WaqfReader/app/src/main/assets/quran_words_with_waqf.json"
    out_assets.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Writing {out_assets}...")
    with open(out_assets, "w", encoding="utf-8") as f:
        json.dump(enriched_words, f, ensure_ascii=False, indent=1)
    print(f"    File size: {out_assets.stat().st_size / (1024*1024):.2f} MB")

    print("\n[✓] Successfully generated quran-words-with-waqf.json!")


if __name__ == "__main__":
    main()
