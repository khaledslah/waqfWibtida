#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Quran Repeated Words Dataset.

Extracts within-ayah repeated and morphologically similar words across the entire Quran.
Handles:
- Exact duplicate words (e.g. دكاً دكا، صفا صفا، هيهات هيهات)
- Prefix variations (e.g. الله / لله، الناس / للناس، الحر / بالحر)
- Stem/inflection variations (e.g. الخبيثات / للخبيثين، ربه / لرب)

Outputs:
- data/quran_repeated_words.json
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 114 Surah Names
SURAH_NAMES = {
    1: "الفاتحة", 2: "البقرة", 3: "آل عمران", 4: "النساء", 5: "المائدة", 6: "الأنعام",
    7: "الأعراف", 8: "الأنفال", 9: "التوبة", 10: "يونس", 11: "هود", 12: "يوسف",
    13: "الرعد", 14: "إبراهيم", 15: "الحجر", 16: "النحل", 17: "الإسراء", 18: "الكهف",
    19: "مريم", 20: "طه", 21: "الأنبياء", 22: "الحج", 23: "المؤمنون", 24: "النور",
    25: "الفرقان", 26: "الشعراء", 27: "النمل", 28: "القصص", 29: "العنكبوت", 30: "الروم",
    31: "لقمان", 32: "السجدة", 33: "الأحزاب", 34: "سبأ", 35: "فاطر", 36: "يس",
    37: "الصافات", 38: "ص", 39: "الزمر", 40: "غافر", 41: "فصلت", 42: "الشورى",
    43: "الزخرف", 44: "الدخان", 45: "الجاثية", 46: "الأحقاف", 47: "محمد", 48: "الفتح",
    49: "الحجرات", 50: "ق", 51: "الذاريات", 52: "الطور", 53: "النجم", 54: "القمر",
    55: "الرحمن", 56: "الواقعة", 57: "الحديد", 58: "المجادلة", 59: "الحشر", 60: "الممتحنة",
    61: "الصف", 62: "الجمعة", 63: "المنافقون", 64: "التغابن", 65: "الطلاق", 66: "التحريم",
    67: "الملك", 68: "القلم", 69: "الحاقة", 70: "المعارج", 71: "نوح", 72: "الجن",
    73: "المزمل", 74: "المدثر", 75: "القيامة", 76: "الإنسان", 77: "المرسلات", 78: "النبأ",
    79: "النازعات", 80: "عبس", 81: "التكوير", 82: "الانفطار", 83: "المطففين", 84: "الانشقاق",
    85: "البروج", 86: "الطارق", 87: "الأعلى", 88: "الغاشية", 89: "الفجر", 90: "البلد",
    91: "الشمس", 92: "الليل", 93: "الضحى", 94: "الشرح", 95: "التين", 96: "العلق",
    97: "القدر", 98: "البينة", 99: "الزلزلة", 100: "العاديات", 101: "القارعة", 102: "التكاثر",
    103: "العصر", 104: "الهمزة", 105: "الفيل", 106: "قريش", 107: "الماعون", 108: "الكوثر",
    109: "الكافرون", 110: "النصر", 111: "المسد", 112: "الإخلاص", 113: "الفلق", 114: "الناس"
}

_STRIP = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640۞۩ۚۖۗۘۙۛۜ]")

ALLAH_SET = {
    "الله", "لله", "بالله", "ولله", "فلله", "تالله", "اللهم", "والله", "فالله", "وبالله", "تالله"
}

PARTICLES = {
    "في", "من", "ما", "لا", "ان", "انما", "على", "الى", "عن", "ثم", "او", "ام",
    "بل", "حتى", "اذا", "اذ", "هو", "هي", "هم", "هن", "انت", "انتم", "انا", "نحن",
    "ذا", "ذو", "ذي", "ذات", "هذا", "هذه", "هؤلاء", "ذلك", "تلك", "اولئك",
    "الذي", "التي", "الذين", "اللاتي", "اللواتي", "الا", "يا", "ايها", "ايتها",
    "كان", "كانوا", "يكون", "تكون", "و", "ف", "ب", "ل", "ك", "قد", "لو", "لما",
    "كل", "غير", "مع", "دون", "بين"
}


def norm(text: str) -> str:
    """Normalize Arabic text for consonantal comparison."""
    if not text:
        return ""
    t = _STRIP.sub("", text)
    t = t.replace("ٱ", "ا").replace("إ", "ا").replace("أ", "ا").replace("آ", "ا")
    t = t.replace("ة", "ه").replace("ى", "ي")
    return t.strip()


def get_base_stem(text: str) -> str:
    """
    Extract base stem by stripping standard proclitics and enclitics.
    Unifies Allah / Lillah / Billah into 'الله'.
    """
    n = norm(text)
    if not n:
        return ""
    if n in ALLAH_SET:
        return "الله"
    if n in PARTICLES:
        return n

    # Special handling for 'رب'
    if n in ("رب", "ربه", "ربها", "ربهم", "ربكم", "ربنا", "ربي", "لرب", "لربه", "لربهم", "برب", "بربكم", "ورب", "وربنا"):
        return "رب"

    t = n

    # 1. Strip conjunctions (و / ف) if remainder is substantial
    if (t.startswith("و") or t.startswith("ف")) and len(t) >= 4:
        if t[1:] in ALLAH_SET:
            return "الله"
        t = t[1:]

    # 2. Definite article and preposition combinations
    if t.startswith("بال") and len(t) >= 5:
        t = t[3:]
    elif t.startswith("كال") and len(t) >= 5:
        t = t[3:]
    elif t.startswith("لل") and len(t) >= 4:
        t = t[2:]
    elif t.startswith("ال") and len(t) >= 4:
        t = t[2:]
    elif (t.startswith("ب") or t.startswith("ك") or t.startswith("ل")) and len(t) >= 4:
        if not (t.startswith("بين") or t.startswith("بعض") or t.startswith("بل") or t.startswith("لبث")):
            t = t[1:]

    # 3. Suffixes (plural, dual, possessive pronouns)
    for sfx in ("هم", "هن", "كم", "كن", "نا", "ها", "ون", "ين", "ات", "ان"):
        if t.endswith(sfx) and len(t) - len(sfx) >= 3:
            t = t[:-len(sfx)]
            break

    # 4. Single-letter suffixes (ه, ك, ي, ت)
    if (t.endswith("ه") or t.endswith("ك") or t.endswith("ي") or t.endswith("ت")) and len(t) >= 4:
        t = t[:-1]

    return t


def main():
    print("[*] Loading quran-words-uthmani-waqf.json...")
    words_file = ROOT / "quran-words-uthmani-waqf.json"
    if not words_file.exists():
        words_file = ROOT / "quran-words.json"
    words = json.load(open(words_file, encoding="utf-8"))
    print(f"    Loaded {len(words)} words.")

    # Group words by (surah, ayah)
    words_by_ayah = defaultdict(list)
    for idx, w in enumerate(words):
        words_by_ayah[(w["s"], w["v"])].append((idx + 1, w))

    all_groups = []
    group_counter = 0

    for (s, v), ayah_w_list in words_by_ayah.items():
        stem_groups = defaultdict(list)

        for global_id, w in ayah_w_list:
            clean_word = norm(w.get("clean_u") or w["u"])
            base_stem = get_base_stem(clean_word)
            if len(base_stem) >= 2:
                stem_groups[base_stem].append((global_id, w, clean_word))

        for base_stem, members in stem_groups.items():
            if len(members) >= 2:
                group_counter += 1
                is_particle = base_stem in PARTICLES
                clean_forms = [m[2] for m in members]
                unique_forms = sorted(list(set(clean_forms)))
                is_exact = len(unique_forms) == 1

                # Check adjacency
                positions = [m[1]["p"] for m in members]
                is_adjacent = any(positions[i + 1] == positions[i] + 1 for i in range(len(positions) - 1))

                # Determine match type
                if is_exact:
                    match_type = "exact"
                elif base_stem == "الله" or any(c.startswith("ال") or c.startswith("ل") or c.startswith("ب") or c.startswith("و") for c in clean_forms):
                    match_type = "prefix_variant"
                else:
                    match_type = "stem_variant"

                group_id = f"s{s}-a{v}-g{group_counter}"
                word_entries = []
                for global_id, w_data, c_form in members:
                    p = w_data["p"]
                    w_id = f"s{s}-a{v}-w{p}"
                    word_entries.append({
                        "wordId": w_id,
                        "globalId": global_id,
                        "position": p,
                        "text": w_data.get("clean_u") or w_data["u"],
                        "textUthmani": w_data["u"],
                        "textImlai": w_data.get("i"),
                        "clean": c_form
                    })

                group_obj = {
                    "groupId": group_id,
                    "surah": s,
                    "ayah": v,
                    "surahName": SURAH_NAMES.get(s, f"سورة {s}"),
                    "ayahRef": f"{s}:{v}",
                    "baseStem": base_stem,
                    "matchType": match_type,
                    "isParticle": is_particle,
                    "isAdjacent": is_adjacent,
                    "wordCount": len(members),
                    "distinctForms": unique_forms,
                    "wordIds": [w["wordId"] for w in word_entries],
                    "words": word_entries
                }
                all_groups.append(group_obj)

    # Compute Statistics
    ayahs_with_reps = len(set((g["surah"], g["ayah"]) for g in all_groups))
    content_groups = [g for g in all_groups if not g["isParticle"]]
    exact_groups = [g for g in all_groups if g["matchType"] == "exact"]
    prefix_groups = [g for g in all_groups if g["matchType"] == "prefix_variant"]
    stem_groups_list = [g for g in all_groups if g["matchType"] == "stem_variant"]
    adjacent_groups = [g for g in all_groups if g["isAdjacent"]]

    output_payload = {
        "schemaVersion": "1.0.0",
        "description": "Corpus of repeated and morphologically similar words in the same Ayah across the Quran",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "totalWordsAnalyzed": len(words),
            "totalAyahsWithRepetitions": ayahs_with_reps,
            "totalRepetitionGroups": len(all_groups),
            "contentWordGroups": len(content_groups),
            "particleGroups": len(all_groups) - len(content_groups),
            "exactMatches": len(exact_groups),
            "prefixVariants": len(prefix_groups),
            "stemVariants": len(stem_groups_list),
            "adjacentRepetitions": len(adjacent_groups)
        },
        "groups": all_groups
    }

    out_file = ROOT / "data" / "quran_repeated_words.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(f"[+] Successfully generated dataset: {out_file.resolve()}")
    print(f"    File size: {out_file.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"    Total repetition groups: {len(all_groups)}")
    print(f"    Content word groups: {len(content_groups)}")
    print(f"    Exact repetitions: {len(exact_groups)}")
    print(f"    Prefix variants (like الله/لله): {len(prefix_groups)}")
    print(f"    Adjacent duplicates: {len(adjacent_groups)}")


if __name__ == "__main__":
    main()
