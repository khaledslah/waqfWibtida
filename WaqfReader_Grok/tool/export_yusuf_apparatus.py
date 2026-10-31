#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export Yusuf 100–111 from production apparatus_v4 JSON into a Flutter asset."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(r"D:\AI_Projects\waqfWibtida2")
OUT_DIR = ROOT / "sajawandi_vlm_work" / "compare_agent_vs_vlm" / "_full_run" / "out"
ASSET = ROOT / "WaqfReader_Grok" / "assets" / "yusuf_100_111_apparatus.json"
GENERATED = (
    ROOT / "WaqfReader_Grok" / "lib" / "data" / "yusuf_apparatus_generated.dart"
)

BATCHES = [
    "batch_607_610.apparatus_v4.raw.json",  # covers 100–111 on 607–609
]

# Prefer plain production file (not antigravity) for overlapping ranges.
AYAH_MIN, AYAH_MAX = 100, 111
SURAH = 12

LABEL_TO_SYMBOL = {
    "ط": "tam",
    "م": "lazim",  # map to tam-ish in app? app has no lazim — use unsettled or tam
    "ج": "jaiz",
    "ز": "mujawwaz",
    "ص": "jaiz",  # حسن → treat as jaiz badge for demo palette
    "لا": "la",
    "ق": "unsettled",
}

VERDICT_TO_LABEL_AR = {
    "تام": "تام",
    "لازم": "لازم",
    "جائز": "جائز",
    "حسن": "حسن",
    "لا يوقف": "لا يوقف",
    "قيل فيه وقف": "قيل فيه وقف",
}

# Uthmani word lists for 12:100–111 (from existing sample_data / Tanzil-style).
# Keep display text with harakat; matching uses stripped forms.
AYAH_WORDS: dict[int, list[str]] = {
    100: [
        "وَرَفَعَ", "أَبَوَيْهِ", "عَلَى", "الْعَرْشِ", "وَخَرُّوا", "لَهُ", "سُجَّدًا",
        "وَقَالَ", "يَاأَبَتِ", "هَٰذَا", "تَأْوِيلُ", "رُؤْيَايَ", "مِن", "قَبْلُ",
        "قَدْ", "جَعَلَهَا", "رَبِّي", "حَقًّا", "وَقَدْ", "أَحْسَنَ", "بِي", "إِذْ",
        "أَخْرَجَنِي", "مِنَ", "السِّجْنِ", "وَجَاءَ", "بِكُم", "مِنَ", "الْبَدْوِ",
        "مِن", "بَعْدِ", "أَن", "نَزَغَ", "الشَّيْطَانُ", "بَيْنِي", "وَبَيْنَ", "إِخْوَتِي",
        "إِنَّ", "رَبِّي", "لَطِيفٌ", "لِمَا", "يَشَاءُ", "إِنَّهُ", "هُوَ", "الْعَلِيمُ",
        "الْحَكِيمُ",
    ],
    101: [
        "رَبِّ", "قَدْ", "آتَيْتَنِي", "مِنَ", "الْمُلْكِ", "وَعَلَّمْتَنِي", "مِن",
        "تَأْوِيلِ", "الْأَحَادِيثِ", "فَاطِرَ", "السَّمَاوَاتِ", "وَالْأَرْضِ", "أَنْتَ",
        "وَلِيِّي", "فِي", "الدُّنْيَا", "وَالْآخِرَةِ", "تَوَفَّنِي", "مُسْلِمًا",
        "وَأَلْحِقْنِي", "بِالصَّالِحِينَ",
    ],
    102: [
        "ذَٰلِكَ", "مِنْ", "أَنْبَاءِ", "الْغَيْبِ", "نُوحِيهِ", "إِلَيْكَ", "وَمَا",
        "كُنْتَ", "لَدَيْهِمْ", "إِذْ", "أَجْمَعُوا", "أَمْرَهُمْ", "وَهُمْ", "يَمْكُرُونَ",
    ],
    103: ["وَمَا", "أَكْثَرُ", "النَّاسِ", "وَلَوْ", "حَرَصْتَ", "بِمُؤْمِنِينَ"],
    104: [
        "وَمَا", "تَسْأَلُهُمْ", "عَلَيْهِ", "مِنْ", "أَجْرٍ", "إِنْ", "هُوَ", "إِلَّا",
        "ذِكْرٌ", "لِلْعَالَمِينَ",
    ],
    105: [
        "وَكَأَيِّنْ", "مِنْ", "آيَةٍ", "فِي", "السَّمَاوَاتِ", "وَالْأَرْضِ", "يَمُرُّونَ",
        "عَلَيْهَا", "وَهُمْ", "عَنْهَا", "مُعْرِضُونَ",
    ],
    106: ["وَمَا", "يُؤْمِنُ", "أَكْثَرُهُمْ", "بِاللَّهِ", "إِلَّا", "وَهُمْ", "مُشْرِكُونَ"],
    107: [
        "أَفَأَمِنُوا", "أَن", "تَأْتِيَهُمْ", "غَاشِيَةٌ", "مِنْ", "عَذَابِ", "اللَّهِ",
        "أَوْ", "تَأْتِيَهُمُ", "السَّاعَةُ", "بَغْتَةً", "وَهُمْ", "لَا", "يَشْعُرُونَ",
    ],
    108: [
        "قُلْ", "هَٰذِهِ", "سَبِيلِي", "أَدْعُو", "إِلَى", "اللَّهِ", "عَلَىٰ", "بَصِيرَةٍ",
        "أَنَا", "وَمَنِ", "اتَّبَعَنِي", "وَسُبْحَانَ", "اللَّهِ", "وَمَا", "أَنَا", "مِنَ",
        "الْمُشْرِكِينَ",
    ],
    109: [
        "وَمَا", "أَرْسَلْنَا", "مِنْ", "قَبْلِكَ", "إِلَّا", "رِجَالًا", "نُوحِي", "إِلَيْهِمْ",
        "مِنْ", "أَهْلِ", "الْقُرَى", "أَفَلَمْ", "يَسِيرُوا", "فِي", "الْأَرْضِ", "فَيَنْظُرُوا",
        "كَيْفَ", "كَانَ", "عَاقِبَةُ", "الَّذِينَ", "مِنْ", "قَبْلِهِمْ", "وَلَدَارُ",
        "الْآخِرَةِ", "خَيْرٌ", "لِلَّذِينَ", "اتَّقَوْا", "أَفَلَا", "تَعْقِلُونَ",
    ],
    110: [
        "حَتَّىٰ", "إِذَا", "اسْتَيْأَسَ", "الرُّسُلُ", "وَظَنُّوا", "أَنَّهُمْ", "قَدْ",
        "كُذِبُوا", "جَاءَهُمْ", "نَصْرُنَا", "فَنُجِّيَ", "مَنْ", "نَشَاءُ", "وَلَا",
        "يُرَدُّ", "بَأْسُنَا", "عَنِ", "الْقَوْمِ", "الْمُجْرِمِينَ",
    ],
    111: [
        "لَقَدْ", "كَانَ", "فِي", "قَصَصِهِمْ", "عِبْرَةٌ", "لِأُولِي", "الْأَلْبَابِ", "مَا",
        "كَانَ", "حَدِيثًا", "يُفْتَرَىٰ", "وَلَٰكِنْ", "تَصْدِيقَ", "الَّذِي", "بَيْنَ",
        "يَدَيْهِ", "وَتَفْصِيلَ", "كُلِّ", "شَيْءٍ", "وَهُدًى", "وَرَحْمَةً", "لِقَوْمٍ",
        "يُؤْمِنُونَ",
    ],
}


def strip_ar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]", "", s)
    s = s.replace("\u0671", "\u0627").replace("\u0623", "\u0627")
    s = s.replace("\u0625", "\u0627").replace("\u0622", "\u0627")
    s = s.replace("\u0629", "\u0647").replace("\u0649", "\u064a")
    s = s.replace("ٱ", "ا").replace("ٰ", "")
    s = re.sub(r"[^\u0621-\u064A\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def reason_from_text(text: str | None) -> str:
    if not text:
        return ""
    # Drop bracket catalog; keep prose after ﴾ if present.
    m = re.search(r"﴾\s*(.*)$", text, re.S)
    if m and m.group(1).strip():
        return m.group(1).strip().rstrip(".")
    # Strip ﴿...﴾ entirely
    cleaned = re.sub(r"﴿[^﴾]*﴾", "", text).strip()
    cleaned = re.sub(r"\[\s*﴿[^﴾]*﴾\s*\]\(\d+\)\.?", "", cleaned).strip()
    return cleaned or text.strip()


def map_symbol(label: str | None, verdict: str | None) -> tuple[str, str]:
    if label in LABEL_TO_SYMBOL:
        sym = LABEL_TO_SYMBOL[label]
        # App StopSymbol: tam, la, jaiz, mujawwaz, unsettled — map lazim→tam
        if sym == "lazim":
            sym = "tam"
        ar = {
            "tam": "تام",
            "la": "لا",
            "jaiz": "جائز",
            "mujawwaz": "مجوَّز",
            "unsettled": "غير محسوم",
        }[sym]
        if label == "ص":
            ar = "حسن"
        if label == "م":
            ar = "لازم"
        return sym, ar
    if verdict in VERDICT_TO_LABEL_AR:
        v = verdict
        if v == "تام" or v == "لازم":
            return "tam", v
        if v == "لا يوقف":
            return "la", v
        if v == "جائز":
            return "jaiz", v
        if v == "حسن":
            return "jaiz", v
        return "unsettled", v
    return "unsettled", verdict or "غير محسوم"


def find_word_index(ayah: int, target: str) -> int | None:
    words = AYAH_WORDS.get(ayah) or []
    stripped = [strip_ar(w) for w in words]
    t = strip_ar(target)
    if not t:
        return None
    # Exact last-token match for multi-word targets (e.g. من قبل → قَبْلُ)
    parts = t.split()
    needle = parts[-1]
    # Prefer full phrase window match
    if len(parts) > 1:
        n = len(parts)
        for i in range(len(stripped) - n + 1):
            if stripped[i : i + n] == parts:
                return i + n - 1
    # Special: أدعو إلى الله → الله
    for i, w in enumerate(stripped):
        if w == needle:
            return i
    # Fuzzy contains
    for i, w in enumerate(stripped):
        if needle in w or w in needle:
            return i
    return None


def slug(ayah: int, target: str, idx: int) -> str:
    base = strip_ar(target).replace(" ", "-") or f"w{idx}"
    base = re.sub(r"[^a-zA-Z0-9\u0621-\u064A\-]", "", base)
    # ASCII-ish id for Flutter keys
    # Prefer last token of target for stable English-ish ids.
    last = strip_ar(target).split()[-1] if strip_ar(target) else ""
    trans = {
        "سجدا": "sujjadan",
        "قبل": "qablu",
        "حقا": "haqqa",
        "إخوتي": "ikhwati",
        "اخوتي": "ikhwati",
        "يشاء": "yashau",
        "الأحاديث": "ahadith",
        "الاحاديث": "ahadith",
        "إليك": "ilayk",
        "اليك": "ilayk",
        "أجر": "ajr",
        "اجر": "ajr",
        "الله": "allah",
        "اتبعني": "ittabaani",
        "القرى": "qura",
        "القري": "qura",
        "قبلهم": "qablihim",
        "اتقوا": "ittaqaw",
        "نصرنا": "nasr",
        "نشاء": "nashaa",
        "الألباب": "albab",
        "الالباب": "albab",
        "الآخرة": "akhira",
        "الاخرة": "akhira",
        "والآخرة": "akhira",
        "والاخرة": "akhira",
        "والاخره": "akhira",
        "الاخره": "akhira",
    }
    key = trans.get(last) or trans.get(base) or f"w{idx}"
    return f"yusuf-{ayah}-{key}"


def collect_waqfs() -> list[dict]:
    waqfs: list[dict] = []
    for fn in BATCHES:
        path = OUT_DIR / fn
        data = json.loads(path.read_text(encoding="utf-8"))
        for w in data.get("waqfs", []):
            ayah = w.get("ayah")
            if ayah is None or not (AYAH_MIN <= int(ayah) <= AYAH_MAX):
                continue
            waqfs.append(w)
    # Dedup by (ayah, target_word, text_page)
    seen = set()
    uniq = []
    for w in waqfs:
        key = (w.get("ayah"), w.get("target_word"), w.get("text_page"), w.get("text"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(w)
    return uniq


def build_export(waqfs: list[dict]) -> dict:
    stops = []
    # word_index → stop_id per ayah
    attachments: dict[int, dict[int, str]] = {a: {} for a in AYAH_WORDS}

    for w in waqfs:
        ayah = int(w["ayah"])
        target = w.get("target_word") or ""
        idx = find_word_index(ayah, target)
        if idx is None:
            print(f"WARN: unmatched {ayah}:{target!r}")
            continue
        # If already attached, keep first (matn order)
        if idx in attachments[ayah]:
            print(f"WARN: duplicate attach ayah {ayah} idx {idx} ({target})")
            continue

        sid = slug(ayah, target, idx)
        attachments[ayah][idx] = sid

        symbol, label_ar = map_symbol(w.get("verdict_label"), w.get("verdict"))
        reason = reason_from_text(w.get("text"))
        page = w.get("text_page")
        page_s = str(page) if page is not None else None

        opinions = [
            {
                "scholar": "السجاوندي",
                "verdict": w.get("verdict"),
                "book": "علل الوقوف",
                "page": page_s,
                "comment": None,
            }
        ]
        for app in w.get("apparatus") or []:
            for op in app.get("opinions") or []:
                scholar = op.get("scholar") or "unknown"
                if scholar == "unknown":
                    # Keep but surface comment as identity hint
                    scholar = "حاشية المحقق"
                opinions.append(
                    {
                        "scholar": scholar,
                        "verdict": op.get("verdict"),
                        "book": op.get("book") or "علل الوقوف (حاشية)",
                        "page": (
                            str(op["book_ref"])
                            if op.get("book_ref") is not None
                            else (str(app.get("text_page")) if app.get("text_page") else page_s)
                        ),
                        "comment": op.get("comment"),
                    }
                )

        ai_bits = []
        for app in w.get("apparatus") or []:
            sug = app.get("suggested")
            if not sug:
                continue
            for item in sug.get("waqf") or []:
                r = item.get("reason")
                if r:
                    ai_bits.append(r)
            for item in sug.get("ibtida") or []:
                r = item.get("reason")
                if r:
                    ai_bits.append(r)

        stops.append(
            {
                "id": sid,
                "surah": SURAH,
                "ayah": ayah,
                "word": AYAH_WORDS[ayah][idx],
                "wordIndex": idx,
                "targetWord": target,
                "symbol": symbol,
                "label": label_ar,
                "verdictLabel": w.get("verdict_label"),
                "reason": reason or f"وقف السجاوندي: {label_ar}",
                "inUthmaniMushaf": False,
                "opinions": opinions,
                "aiSuggestion": "\n".join(ai_bits) if ai_bits else None,
                "sourceBatch": "batch_607_610.apparatus_v4.raw.json",
            }
        )

    ayahs = []
    for num, words in AYAH_WORDS.items():
        ayahs.append(
            {
                "number": num,
                "words": [
                    {
                        "text": text,
                        "stopId": attachments[num].get(i),
                    }
                    for i, text in enumerate(words)
                ],
            }
        )

    return {
        "schemaVersion": 1,
        "surah": SURAH,
        "surahName": "سورة يوسف",
        "ayahRange": [AYAH_MIN, AYAH_MAX],
        "source": "apparatus_v4 production (Cursor)",
        "sourceFiles": BATCHES,
        "stops": stops,
        "ayahs": ayahs,
    }


def main() -> None:
    waqfs = collect_waqfs()
    print(f"raw waqfs in range: {len(waqfs)}")
    payload = build_export(waqfs)
    ASSET.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ASSET.write_text(text, encoding="utf-8")

    # Sync Dart const so Flutter/tests do not depend on async asset I/O.
    GENERATED.write_text(
        "// GENERATED by tool/export_yusuf_apparatus.py — do not edit by hand.\n"
        "// Source: batch_607_610.apparatus_v4.raw.json (Yusuf 100–111)\n"
        "const String yusufApparatusJson = r'''\n"
        f"{text}"
        "''';\n",
        encoding="utf-8",
    )
    print(f"wrote {ASSET} stops={len(payload['stops'])}")
    print(f"wrote {GENERATED}")
    for s in payload["stops"]:
        n_op = len(s["opinions"])
        print(
            f"  {s['id']:28} a{s['ayah']} {s['label']:8} ops={n_op} ai={bool(s['aiSuggestion'])}"
        )


if __name__ == "__main__":
    main()
