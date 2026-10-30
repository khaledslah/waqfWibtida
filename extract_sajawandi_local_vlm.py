#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Al-Sajawandi Waqf Local VLM & Gemini Vision Batch Processing Pipeline
=====================================================================
Layers (one run):
  1. cache/raw/batch_*.raw.txt  — immutable VLM response (write-once)
  2. extracted candidates       — text/old_text, fixes[], trust axes
  3a. flat corpus JSON          — app-facing entries
  3b. nested surahs mirror      — human review

Trust green (T2, derived in UI):
  vlm_vs_shamela=match AND edit_status=pristine AND mapping_status=mapped
  AND review_status=affirmed (human; default pending)

Shamela is used for T1 compare only.
Symbol fixes require basis=page_prose (from page commentary), never logical inference.
"""

from __future__ import annotations

import os
import sys
import json
import re
import time
import base64
import argparse
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timezone

from PIL import Image

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import fitz
except ImportError:
    fitz = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

if fitz is None and pdfium is None:
    print("[Warning] Neither PyMuPDF (fitz) nor pypdfium2 found. PDF rendering will fail unless installed.")

# ---------------------------------------------------------------------------
# Schema constants (aligned with corpus.ts + locked Sajawandi table)
# ---------------------------------------------------------------------------
BOOK_ID = "Al-Sajawandi-Ilal"
BOOK_META = {
    "book_id": BOOK_ID,
    "title": "علل الوقوف (الإيضاح في الوقف والابتداء)",
    "author": "أبو عبد الله محمد بن طيفور السجاوندي",
    "died_hijri": 560,
    "source": "PDF: علل الوقوف - السجاوندي - ت العيدي 1-3 - KTB_0073685-1-600.pdf",
}

# Locked Sajawandi → app verdict (ط = مطلق/تام, NOT لازم)
VERDICT_MAP = {
    "ط": "تام",
    "م": "لازم",
    "ج": "جائز",
    "ز": "جائز",
    "ص": "حسن",
    "لا": "لا يوقف",
    "ق": "قيل فيه وقف",
}

FIX_TYPE_ENUM = [
    "page_split",
    "missing_delimiter",
    "missing_symbol",
    "orthography",
    "ayah_number_correction",
    "malformed_bracket",
]

SYMBOL_FIX_TYPES = {"missing_symbol"}
FIX_BASIS_ENUM = ["page_prose", "editor_policy"]

TRUST_VLM_SHAMELA = ["match", "mismatch", "no_shamela", "not_checked"]
TRUST_EDIT = ["pristine", "normalized"]
TRUST_MAPPING = ["mapped", "ayah_only", "failed"]
TRUST_REVIEW = ["pending", "affirmed", "rejected"]

DEFAULT_QURAN_WORDS = Path(__file__).resolve().parent / "quran-words.json"
DEFAULT_QURAN_AYAHS = Path(__file__).resolve().parent / "quran-ayahs.json"
DEFAULT_SHAMELA = Path(__file__).resolve().parent / "Al-Sajawandi-Ilal-30007.json"
DEFAULT_SURAH_MAP = Path(__file__).resolve().parent / "sajawandi_surah_page_map.json"

# Preferred order for Gemini fallback (Gemini 3 Flash / 3.5 excluded by product rule)
ALLOWED_GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.8-flash",
]
ANDROID_PAGES = Path(
    r"C:\Users\Khaled\AndroidStudioProjects\WaqfWIbtida\waqf-ibtida-web\public\data\pdf_pages\sajawandi"
)

# Manual part overrides (ayah filters). Other parts are auto-sliced by page count.
PART_PRESETS = {
    (2, 3): {
        "name": "سورة البقرة",
        "start": 226,
        "end": 267,
        "ayah_start": 106,
        "ayah_end": 176,
    },
}


def load_surah_presets(map_path: Path) -> Dict[int, Dict[str, Any]]:
    """Load surah → printed page ranges from Shamela TOC map."""
    if not map_path.exists():
        return {
            1: {"name": "سورة الفاتحة", "start": 170, "end": 172},
            2: {"name": "سورة البقرة", "start": 173, "end": 357},
        }
    data = json.loads(map_path.read_text(encoding="utf-8"))
    surahs = data.get("surahs") or data
    out: Dict[int, Dict[str, Any]] = {}
    for k, v in surahs.items():
        out[int(k)] = {
            "name": v["name"],
            "start": int(v["start"]),
            "end": int(v["end"]),
        }
    return out


def split_surah_into_parts(
    page_start: int,
    page_end: int,
    pages_per_part: int,
) -> List[Tuple[int, int, int]]:
    """
    Split a surah page span into parts.
    Returns list of (part_number, part_start, part_end), 1-based part numbers.
    """
    if pages_per_part <= 0:
        return [(1, page_start, page_end)]
    parts: List[Tuple[int, int, int]] = []
    p = page_start
    n = 1
    while p <= page_end:
        pe = min(p + pages_per_part - 1, page_end)
        parts.append((n, p, pe))
        p = pe + 1
        n += 1
    return parts

# Diacritics, Quranic annotation/pause marks, tatweel, bidi, zero-width
SKIPPABLE_MARKS_RE = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u200B-\u200F\u061C\uFEFF\u06DE\u06E2\u06E3\u06EA-\u06ED]"
)
# Keep only Arabic letters after folding (drops leftover pause glyphs / punctuation)
ARABIC_LETTER_RE = re.compile(r"[\u0621-\u064A]")

# Common Sajawandi/mushaf orthography folds applied after letter normalize
ORTHO_FOLDS = (
    ("سموات", "سماوات"),
    ("صلاوه", "صلاه"),  # الصلٰوة
    ("صلوه", "صلاه"),
    ("زكاوه", "زكاه"),  # IndoPak زکٰوة after superscript-alef expand
    ("زكوه", "زكاه"),
    ("زكوة", "زكاه"),
    ("اللاه", "الله"),  # اللّٰه after superscript-alef expand
    ("نصاراي", "نصاري"),  # نصٰرٰى → نصاراي → نصاري
    ("خايفين", "خافين"),  # خائفين after hamza fold
    ("ترضايها", "ترضاها"),  # تَرْضٰٮهَا
    ("عقبيه", "عقبه"),  # عَقِبَيْهِ ↔ عقبه
    ("حيوه", "حياه"),
    ("اليل", "الليل"),
)

EXTRACTION_SYSTEM_PROMPT = """أنت باحث ومحقق لغوي خبير متخصص في تحقيق كتب الوقف والابتداء والقرآن الكريم.
مهمتك استخراج وتوثيق مواضع الوقف بدقة مطلقة من صفحات كتاب «علل الوقوف» للسجاوندي (تحقيق د. محمد بن عبد الله العيدي).

## RAW OUTPUT SCHEMA (strict — no other fields; no post-processing assumed)

Root object:
{
  "page_numbers": [<int>, ...],   // physical printed pages in this batch
  "waqfs": [ <Waqf>, ... ]
}

Waqf object (every key required):
{
  "ayah": <int>,                 // Western digits
  "target_word": <string>,       // pause anchor word(s) from the bracket
  "verdict_label": <Label>,      // letter ONLY — see enum
  "verdict": <Verdict>,          // mapped ruling ONLY — see map
  "text": <string>,              // AFTER fixes: ﴿... - ayah - label﴾ + full ta'lil
  "text_page": <int>,            // page where the bracket starts
  "old_text": <string|null>,     // pre-fix literal if fixes non-empty; else null
  "fixes": <Fix[]>               // empty [] if pristine — NEVER omit; NEVER use singular "fix"
}

Label enum (verdict_label ONLY these):
  "ط" | "م" | "ج" | "ز" | "ص" | "لا" | "ق"

Verdict map (verdict MUST equal map[verdict_label]):
  ط → "تام"
  م → "لازم"
  ج → "جائز"
  ز → "جائز"
  ص → "حسن"
  لا → "لا يوقف"
  ق → "قيل فيه وقف"

Fix object (each element of fixes):
{
  "type": <FixType>,
  "basis": "page_prose" | "editor_policy",
  "old_text": <string>,
  "new_text": <string>,          // must match top-level Waqf.text for that fix set
  "info": <string>
}

FixType enum:
  "page_split" | "missing_delimiter" | "missing_symbol" |
  "orthography" | "ayah_number_correction" | "malformed_bracket"

## RULES
1. Extract every ﴿ ... ﴾ waqf in the matn with its full visible ta'lil (do not drop/condense).
2. verdict_label = Sajawandi letter only. NEVER put تام/حسن/جائز/لا يوقف in verdict_label.
3. verdict = mapped string only. NEVER put ta'lil (لأن...) in verdict. Ta'lil belongs only in text.
4. If pristine: old_text=null and fixes=[].
5. If any fix: old_text = literal pre-fix extract; text = corrected form; fixes has ≥1 object;
   each fix.new_text aligns with final text; fix.old_text is the pre-fix span for that change.
6. missing_symbol (or changing the letter): ONLY if the page commentary states the symbol
   (basis MUST be "page_prose"). Forbidden: inventing a symbol from Quran logic alone.
7. Other FixTypes (page_split, missing_delimiter, orthography, ayah_number_correction,
   malformed_bracket) may use basis "editor_policy" or "page_prose" as appropriate.
8. Return JSON only matching this schema. No markdown fences. No singular "fix" field.

## VALID example (pristine)
{
  "ayah": 113,
  "target_word": "شيء",
  "verdict_label": "ص",
  "verdict": "حسن",
  "text": "﴿النصارى على شيء - 113 - ص﴾ لعطف الجملتين المتفقتين.",
  "text_page": 230,
  "old_text": null,
  "fixes": []
}

## VALID example (with fix)
{
  "ayah": 114,
  "target_word": "خائفين",
      "verdict_label": "ط",
  "verdict": "تام",
  "text": "﴿خائفين - 114 - ط﴾ لأن ما بعده إخبار وعيد...",
  "text_page": 230,
  "old_text": "﴿خائفين - 114 - ط﴾ لأن ما بعده إخبار وعيد...",
  "fixes": [
    {
        "type": "page_split",
      "basis": "editor_policy",
      "old_text": "﴿خائفين - 114 - ط﴾ لأن ما بعده إخبار وعيد...",
      "new_text": "﴿خائفين - 114 - ط﴾ لأن ما بعده إخبار وعيد...",
      "info": "انقطاع التعليل بين صفحتين"
    }
  ]
}

## INVALID (do not emit)
{ "verdict_label": "حسن", "verdict": "لأن الواو للحال", "fix": null }
"""


# ---------------------------------------------------------------------------
# Arabic normalize + Quran word index
# ---------------------------------------------------------------------------
def fold_arabic_char(ch: str) -> Optional[str]:
    # Superscript alef handled in normalize_arabic (avoid اا after base alef)
    if ch == "\u0670":
        return "ا"
    if SKIPPABLE_MARKS_RE.match(ch):
        return None
    if ch in "أإآٱ":
        return "ا"
    if ch in "ىیۍ":  # alif maqsura + Farsi yeh variants
        return "ي"
    if ch == "ة":
        return "ه"
    if ch in "کڪ":  # keheh (IndoPak mushaf) → kaf
        return "ك"
    if ch == "\u066E":  # dotless beh often encodes ئ/ي in IndoPak orthography
        return "ي"
    if ch == "ھ":
        return "ه"
    if ch == "ؤ":
        return "و"
    if ch == "ئ":
        return "ي"
    if ch == "ء":
        return ""
    return ch


def normalize_arabic(text: Optional[str]) -> str:
    """Strip tashkeel/pause marks; fold hamza/alef/ya/ta-marbuta; keep Arabic letters + spaces."""
    if not text:
        return ""
    out: List[str] = []
    prev_space = True
    for ch in text:
        if ch == "~" or ch.isspace():
            # Drop space only when buffer is exactly a clitic (IndoPak: "وَ يزكيهم")
            so_far = "".join(out).strip()
            if so_far in ("و", "ف", "ب", "ك", "ل", "ال", "وال", "بال", "فال", "كال", "لل"):
                continue
            if not prev_space:
                out.append(" ")
                prev_space = True
            continue
        folded = fold_arabic_char(ch)
        if folded is None or folded == "":
            continue
        if not ARABIC_LETTER_RE.match(folded):
            continue
        # Skip superscript/base alef doubling: اٰ → ا not اا
        if folded == "ا" and out and out[-1] == "ا":
            prev_space = False
            continue
        out.append(folded)
        prev_space = False
    if out and out[-1] == " ":
        out.pop()
    s = "".join(out)
    s = s.replace("اا", "ا")
    for a, b in ORTHO_FOLDS:
        s = s.replace(a, b)
    return s


def strip_arabic_clitics(token: str) -> List[str]:
    """Return token plus progressive bare forms after common prefixes (و/ف/ب/ك/ل/ال)."""
    forms = [token]
    t = token
    # peel conjunction / prep / article greedily
    changed = True
    while changed and len(t) > 2:
        changed = False
        for pref in ("وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ك", "ل"):
            if t.startswith(pref) and len(t) - len(pref) >= 2:
                t = t[len(pref) :]
                forms.append(t)
                changed = True
                break
    return forms


def normalize_mushaf_token(text: Optional[str]) -> str:
    """Normalize one mushaf word entry; always collapse internal spaces (IndoPak artifacts)."""
    return normalize_arabic(text).replace(" ", "")


def load_quran_words(path: Path) -> Dict[Tuple[int, int], List[Dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by_sv: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
    for w in data:
        by_sv[(int(w["s"]), int(w["v"]))].append(w)
    for key in by_sv:
        by_sv[key].sort(key=lambda x: int(x["p"]))
    return by_sv


def load_shamela_pages(path: Optional[Path]) -> Dict[int, str]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    pages = data.get("pages") or []
    out: Dict[int, str] = {}
    for p in pages:
        try:
            out[int(p["page"])] = p.get("text") or ""
        except (KeyError, TypeError, ValueError):
            continue
    return out


def phrase_tokens_from_waqf(target_word: str, text: str) -> List[str]:
    """
    Tokens from Sajawandi target / ﴿phrase - ayah - code﴾.
    Prefer bracket phrase before ayah number; fall back to target_word.
    """
    inside = text or ""
    m = re.search(r"﴿([^﴾]+)﴾", inside)
    if m:
        inside = m.group(1)
    phrase = re.split(r"[-–—\s_]+[٠-٩0-9]+", inside, maxsplit=1)[0]
    phrase = re.sub(r"(الأولى|الأول|الثانية|الثاني|الثالثة|الثالث)", "", phrase)
    tokens = [t for t in normalize_arabic(phrase).split() if t]
    if not tokens and target_word:
        tokens = [t for t in normalize_arabic(target_word).split() if t]
    return tokens


def _token_eq_or_affix(mushaf_tok: str, query_tok: str) -> bool:
    """
    Exact match, or affix match via known clitics only
    (العقود ↔ بالعقود / العقود ↔ والعقود) — NOT arbitrary endswith.
    """
    if not mushaf_tok or not query_tok:
        return False
    if mushaf_tok == query_tok:
        return True
    q_forms = set(strip_arabic_clitics(query_tok))
    m_forms = set(strip_arabic_clitics(mushaf_tok))
    if q_forms & m_forms:
        return True
    # One side is the other plus a known clitic prefix already peeled into forms;
    # also allow query stem as suffix of mushaf only when stem length >= 4
    # and mushaf == prefix + stem for a known single-letter clitic.
    for q in q_forms:
        if len(q) < 4:
            continue
        for m in m_forms:
            if m.endswith(q) and m[: len(m) - len(q)] in ("", "و", "ف", "ب", "ك", "ل", "ال", "وال", "بال", "فال", "كال", "لل"):
                return True
            if q.endswith(m) and q[: len(q) - len(m)] in ("", "و", "ف", "ب", "ك", "ل", "ال", "وال", "بال", "فال", "كال", "لل"):
                return True
    return False


def find_word_match(
    surah: int,
    ayah: int,
    tokens: List[str],
    by_sv: Dict[Tuple[int, int], List[Dict[str, Any]]],
    prev_word: int = 0,
) -> Optional[Dict[str, Any]]:
    """
    Map Sajawandi target into mushaf word within (surah, ayah) only:

      أ) Exact match on a single token
      ب) Affix/suffix match (clitics و/ب/ف/ال …)
      ج) Multi-word phrase → bind to the LAST token of the matched span
         (waqf falls on the last phonetic segment)

    Among multiple hits, prefer word position > prev_word (reading order).
    """
    ayah_words = by_sv.get((surah, ayah)) or []
    if not ayah_words:
        return None
    if not tokens:
        return None

    norms = [
        normalize_mushaf_token(w.get("i") or "") or normalize_mushaf_token(w.get("u") or "")
        for w in ayah_words
    ]

    matches: List[Dict[str, Any]] = []

    # ج) Phrase first (longest sequence), bind to last word of span
    if len(tokens) >= 2:
        for length in range(min(len(tokens), 8), 1, -1):
            needle = tokens[-length:]  # prefer trailing phrase near the stop
            nlen = len(needle)
            found: List[Dict[str, Any]] = []
            for i in range(len(norms) - nlen + 1):
                if all(_token_eq_or_affix(norms[i + j], needle[j]) for j in range(nlen)):
                    found.append(ayah_words[i + nlen - 1])
            if found:
                matches = found
                break

    # أ + ب) Single-token exact / affix — use last query token (stop word)
    if not matches:
        q = tokens[-1]
        for i, n in enumerate(norms):
            if _token_eq_or_affix(n, q):
                matches.append(ayah_words[i])

    # Also try full target as one glued token (لاريب)
    if not matches and len(tokens) >= 2:
        glued = "".join(tokens)
        for i, n in enumerate(norms):
            if _token_eq_or_affix(n, glued) or glued == n:
                matches.append(ayah_words[i])

    if not matches:
        return None
    chosen = next((m for m in matches if int(m["p"]) > prev_word), None)
    return chosen or matches[0]


def shamela_compare(probe: str, page_num: Optional[int], shamela: Dict[int, str]) -> str:
    if not shamela:
        return "no_shamela"
    if page_num is None or page_num not in shamela:
        return "not_checked"
    page_norm = normalize_arabic(shamela[page_num])
    probe_norm = normalize_arabic(probe)
    if not probe_norm:
        return "not_checked"
    # Use a stable core: bracket content or first ~40 chars of normalized probe
    m = re.search(r"﴿([^﴾]+)﴾", probe or "")
    core = normalize_arabic(m.group(1) if m else probe_norm[:80])
    core = re.sub(r"\s+", "", core)
    page_compact = re.sub(r"\s+", "", page_norm)
    if core and core in page_compact:
        return "match"
    # fallback: last significant token
    toks = [t for t in probe_norm.split() if len(t) >= 3]
    if toks and toks[0] in page_norm and (toks[-1] in page_norm):
        return "match"
    return "mismatch"


# ---------------------------------------------------------------------------
# PDF / images
# ---------------------------------------------------------------------------
def get_page_images(
    pages: List[int],
    search_dirs: List[Path],
    pdf_path: Optional[str] = None,
    render_output_dir: Optional[Path] = None,
    dpi: int = 200,
) -> Dict[int, Path]:
    page_to_img: Dict[int, Path] = {}
    missing_pages: List[int] = []

    for p in pages:
        found = False
        candidates = [
            f"page_{p}.png",
            f"page_{p:04d}.png",
            f"page_{p}.jpg",
            f"page_{p:04d}.jpg",
            f"{p}.png",
            f"{p:04d}.png",
            f"{p}.jpg",
            f"{p:04d}.jpg",
        ]
        for s_dir in search_dirs:
            if not s_dir.exists():
                continue
            for cand in candidates:
                cand_path = s_dir / cand
                if cand_path.exists() and cand_path.stat().st_size > 1000:
                    page_to_img[p] = cand_path
                    found = True
                    break
            if found:
                break
        if not found:
            missing_pages.append(p)

    if missing_pages:
        if not pdf_path or not Path(pdf_path).exists():
            raise FileNotFoundError(
                f"Missing {len(missing_pages)} page images ({missing_pages[:5]}...) and PDF not found at {pdf_path}"
            )
        print(f"[*] Rendering {len(missing_pages)} missing PDF pages from {pdf_path}...")
        render_dir = render_output_dir or search_dirs[0]
        render_dir.mkdir(parents=True, exist_ok=True)
        if fitz is not None:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            for p in missing_pages:
                idx = p - 1
                if 0 <= idx < total_pages:
                    pix = doc[idx].get_pixmap(dpi=dpi)
                    img_path = render_dir / f"page_{p}.png"
                    pix.save(str(img_path))
                    page_to_img[p] = img_path
            doc.close()
        elif pdfium is not None:
            pdf = pdfium.PdfDocument(pdf_path)
            total_pages = len(pdf)
            scale = dpi / 72.0
            for p in missing_pages:
                idx = p - 1
                if 0 <= idx < total_pages:
                    bitmap = pdf[idx].render(scale=scale)
                    img_path = render_dir / f"page_{p}.png"
                    bitmap.to_pil().save(img_path)
                    page_to_img[p] = img_path
    else:
        print(f"[*] All {len(pages)} page images found. No PDF re-rendering needed!")

    return page_to_img


def create_2x2_grid(images: List[Path], output_path: Path) -> Path:
    imgs = [Image.open(p) for p in images]
    if not imgs:
        raise ValueError("No images provided for grid creation.")
    w = max(img.width for img in imgs)
    h = max(img.height for img in imgs)
    grid = Image.new("RGB", (w * 2, h * 2), color=(255, 255, 255))
    positions = [(0, 0), (w, 0), (0, h), (w, h)]
    for idx, img in enumerate(imgs[:4]):
        grid.paste(img, positions[idx])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output_path, quality=92)
    return output_path


# ---------------------------------------------------------------------------
# VLM callers
# ---------------------------------------------------------------------------
def build_gemini_model_chain(preferred: Optional[str] = None) -> List[str]:
    """Primary model first, then the rest of the allowlist as fallbacks."""
    chain: List[str] = []
    if preferred and preferred in ALLOWED_GEMINI_MODELS:
        chain.append(preferred)
    for m in ALLOWED_GEMINI_MODELS:
        if m not in chain:
            chain.append(m)
    return chain or list(ALLOWED_GEMINI_MODELS)


def call_gemini_vision_rest(
    image_paths: List[Path],
    prompt: str,
    api_keys: List[str],
    model_name: str = "gemini-3.6-flash",
    model_fallback: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Call Gemini Vision with key rotation + model fallback.
    Returns (response_text, model_used).
    On 429/5xx after trying keys for the current model, falls back to the next model.
    """
    parts: List[Dict[str, Any]] = [{"text": prompt}]
    for img_path in image_paths:
        with open(img_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
        mime = "image/jpeg" if img_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
        parts.append({"inline_data": {"mime_type": mime, "data": b64_img}})

    payload = {
        "system_instruction": {"parts": [{"text": EXTRACTION_SYSTEM_PROMPT}]},
        "contents": [{"parts": parts}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1},
    }
    req_bytes = json.dumps(payload).encode("utf-8")

    models = model_fallback or build_gemini_model_chain(model_name)
    if not api_keys:
        raise RuntimeError("No Gemini API keys configured")

    last_err: Optional[Exception] = None
    for mi, model in enumerate(models):
        # Per model: rotate through keys a few times before falling back
        attempts_per_model = max(len(api_keys) * 2, 4)
        print(f"  [Model] Trying {model} ({mi+1}/{len(models)})...", flush=True)
        for attempt in range(attempts_per_model):
        key = api_keys[attempt % len(api_keys)]
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={key}"
            )
            req = urllib.request.Request(
                url, data=req_bytes, headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                    text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    if mi > 0:
                        print(f"  [Fallback OK] Succeeded with {model}", flush=True)
                    return text, model
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
                last_err = e
            if e.code == 429:
                    wait_t = 8 * ((attempt % 3) + 1)
                    print(
                        f"  [429 {model} key{(attempt % len(api_keys))+1}] "
                        f"wait {wait_t}s ({attempt+1}/{attempts_per_model})",
                        flush=True,
                    )
                time.sleep(wait_t)
            elif e.code >= 500:
                    print(f"  [Server {e.code} {model}] Waiting 6s...", flush=True)
                    time.sleep(6)
            else:
                    print(f"  [HTTP {e.code} {model}] {err_body[:160]}", flush=True)
                    time.sleep(3)
        except Exception as e:
                last_err = e
            time.sleep(3)
        if mi + 1 < len(models):
            print(f"  [Fallback] {model} exhausted → next model", flush=True)

    raise RuntimeError(
        f"Gemini Vision failed for models {models} after key+model fallback: {last_err}"
    )


def call_openai_vision(
    image_paths: List[Path],
    prompt: str,
    api_key: str,
    base_url: Optional[str] = None,
    model_name: str = "gpt-4o",
) -> str:
        from openai import OpenAI

    client = OpenAI(api_key=api_key or "local", base_url=base_url)
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img_path in image_paths:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime = "image/jpeg" if img_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}})
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def robust_json_loads(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    candidate = m.group(1) if m else None
    if not candidate:
        m = re.search(r"(\{.*\})", s, re.DOTALL)
        candidate = m.group(1) if m else s
    cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    for attempt_close in ["}", "]}", "]}}", "]}}}"]:
        try:
            return json.loads(cleaned + attempt_close)
        except Exception:
            pass
    raise json.JSONDecodeError("Failed to parse JSON after robust cleaning", s, 0)


# ---------------------------------------------------------------------------
# Immutable raw layer
# ---------------------------------------------------------------------------
def raw_paths(raw_dir: Path, batch_pages: List[int]) -> Tuple[Path, Path]:
    stem = f"batch_{batch_pages[0]}_{batch_pages[-1]}"
    return raw_dir / f"{stem}.raw.txt", raw_dir / f"{stem}.meta.json"


def index_raw_page_coverage(raw_dir: Path) -> Dict[int, Path]:
    """Map each printed page → raw.txt that already covers it (from meta.json)."""
    coverage: Dict[int, Path] = {}
    if not raw_dir.exists():
        return coverage
    for meta_path in sorted(raw_dir.glob("batch_*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        raw_file = meta_path.with_suffix("").with_suffix(".raw.txt")
        # batch_X_Y.meta.json → batch_X_Y.raw.txt
        raw_file = raw_dir / (meta_path.name.replace(".meta.json", ".raw.txt"))
        if not raw_file.exists():
            continue
        for p in meta.get("pages") or []:
            try:
                coverage[int(p)] = raw_file
            except (TypeError, ValueError):
                continue
    return coverage


def load_waqfs_from_raw_file(raw_file: Path) -> List[Dict[str, Any]]:
    try:
        data = robust_json_loads(raw_file.read_text(encoding="utf-8"))
        return data.get("waqfs") or []
    except Exception as e:
        print(f"  [Parse Error] {raw_file.name}: {e}")
        return []


def collect_raw_waqfs_for_page_range(raw_dir: Path, page_start: int, page_end: int) -> List[Dict[str, Any]]:
    """Load waqfs from every raw file that intersects [page_start, page_end] (deduped by file)."""
    coverage = index_raw_page_coverage(raw_dir)
    files: List[Path] = []
    seen = set()
    for p in range(page_start, page_end + 1):
        f = coverage.get(p)
        if f and f not in seen:
            seen.add(f)
            files.append(f)
    waqfs: List[Dict[str, Any]] = []
    for f in files:
        print(f"  [Raw Load] {f.name}")
        waqfs.extend(load_waqfs_from_raw_file(f))
    return waqfs


def load_or_fetch_raw(
    batch_pages: List[int],
    rendered_images: List[Path],
    use_grid: bool,
    backend: str,
    api_keys: List[str],
    base_url: Optional[str],
    model_name: str,
    raw_dir: Path,
    grid_dir: Path,
    rerun_vlm: bool,
    model_fallback: Optional[List[str]] = None,
) -> str:
    """Return exact VLM text. Writes raw once; never mutates existing raw unless --rerun-vlm."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file, meta_file = raw_paths(raw_dir, batch_pages)

    if raw_file.exists() and not rerun_vlm:
        print(f"  [Raw Hit] {raw_file.name} (immutable; skipping API)")
        return raw_file.read_text(encoding="utf-8")

    if raw_file.exists() and rerun_vlm:
        print(f"  [Raw Rerun] Replacing {raw_file.name} (--rerun-vlm)")

    chain = model_fallback or build_gemini_model_chain(model_name)
    print(
        f"  [VLM] Pages {batch_pages[0]}..{batch_pages[-1]} via {backend} "
        f"(primary={model_name}; fallback={chain})",
        flush=True,
    )
    if use_grid and len(rendered_images) > 1:
        grid_path = grid_dir / f"grid_{batch_pages[0]}_{batch_pages[-1]}.jpg"
        create_2x2_grid(rendered_images, grid_path)
        input_images = [grid_path]
    else:
        input_images = rendered_images

    prompt = (
        f"استخرج جميع مواضع الوقف الواردة في الصفحات المرفقة "
        f"(أرقام الصفحات الفيزيائية المطبوعة: {batch_pages}) وفق التعليمات بدقة تامة."
    )

    used_model = model_name
        try:
            if backend == "gemini":
            raw_response, used_model = call_gemini_vision_rest(
                input_images,
                prompt,
                api_keys,
                model_name=model_name,
                model_fallback=chain,
            )
            else:
            raw_response = call_openai_vision(
                input_images,
                prompt,
                api_keys[0] if api_keys else "local",
                base_url,
                model_name=model_name,
            )
        if not raw_response or not str(raw_response).strip():
            raise ValueError("Empty VLM response")
        except Exception as e:
        raise RuntimeError(f"VLM failed for pages {batch_pages}: {e}") from e

    # Write-once semantics: only write if missing, or explicit rerun
    if not raw_file.exists() or rerun_vlm:
        raw_file.write_text(raw_response, encoding="utf-8")
        meta = {
            "pages": batch_pages,
            "backend": backend,
            "model": used_model,
            "model_primary": model_name,
            "model_chain": chain if backend == "gemini" else [model_name],
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "bytes": len(raw_response.encode("utf-8")),
        }
        if not meta_file.exists() or rerun_vlm:
            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [Raw Saved] {raw_file} (model={used_model})")
    return raw_response


# ---------------------------------------------------------------------------
# Fix policy + candidate normalization
# ---------------------------------------------------------------------------
def coerce_fixes(raw_w: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Accept grilled raw `fixes[]` (+ legacy singular `fix` from older prompts)."""
    fixes_in: List[Dict[str, Any]] = []
    if isinstance(raw_w.get("fixes"), list):
        fixes_in = [f for f in raw_w["fixes"] if isinstance(f, dict)]
    elif isinstance(raw_w.get("fix"), dict):
        f = dict(raw_w["fix"])
        if "info" not in f and f.get("description") is not None:
            f["info"] = f.get("description")
        if "new_text" not in f and raw_w.get("text"):
            f["new_text"] = raw_w.get("text")
        if "basis" not in f:
            f["basis"] = "editor_policy"
        fixes_in = [f]

    accepted: List[Dict[str, Any]] = []
    for f in fixes_in:
        ftype = f.get("type") or "malformed_bracket"
        if ftype not in FIX_TYPE_ENUM:
            ftype = "malformed_bracket"
        basis = f.get("basis") or "editor_policy"
        if basis not in FIX_BASIS_ENUM:
            basis = "editor_policy"
        info = f.get("info") if f.get("info") is not None else f.get("description")

        # Symbol fixes must come from page commentary
        if ftype in SYMBOL_FIX_TYPES or (
            ftype == "orthography"
            and re.search(r"(رمز|رمز الوقف|symbol)", str(info or ""), re.I)
        ):
            if ftype in SYMBOL_FIX_TYPES and basis != "page_prose":
                if re.search(r"(تعليل|شرح|كذلك|وقفة|النص على|في العبارة|page_prose)", str(info or "")):
                    basis = "page_prose"
                else:
                    print(f"  [Fix Rejected] symbol fix without page_prose: {info}")
                    continue

        accepted.append(
            {
                "type": ftype,
                "basis": basis,
                "old_text": f.get("old_text"),
                "new_text": f.get("new_text") or raw_w.get("text"),
                "info": info,
            }
        )
    return accepted


def normalize_candidate(
    raw_w: Dict[str, Any],
    surah_num: int,
    seq: int,
    by_sv: Dict[Tuple[int, int], List[Dict[str, Any]]],
    prev_word_by_ayah: Dict[int, int],
    shamela: Dict[int, str],
) -> Dict[str, Any]:
    try:
        ayah = int(raw_w.get("ayah"))
    except (TypeError, ValueError):
        ayah = 0

    label = raw_w.get("verdict_label")
    verdict = VERDICT_MAP.get(label) if label in VERDICT_MAP else raw_w.get("verdict")
    text = raw_w.get("text") or ""
    fixes = coerce_fixes(raw_w)

    # old_text = VLM pre-fix form
    old_text = raw_w.get("old_text")
    if fixes and not old_text:
        old_text = fixes[0].get("old_text")
    if not fixes:
        old_text = None

    target_word = raw_w.get("target_word")
    try:
        text_page = int(raw_w.get("text_page")) if raw_w.get("text_page") is not None else None
    except (TypeError, ValueError):
        text_page = None

    tokens = phrase_tokens_from_waqf(target_word or "", text)
    prev = prev_word_by_ayah.get(ayah, 0)
    matched = find_word_match(surah_num, ayah, tokens, by_sv, prev_word=prev) if ayah else None

    position = None
    mapping_status = "failed"
    if matched:
        word_pos = int(matched["p"])
        # global word id: 1-based index in flat quran-words is not stored; use running
        # We store word + uthmani; word_id filled later if we have global index map
        position = {
        "surah": surah_num,
            "ayah": ayah,
            "word": word_pos,
            "word_id": matched.get("_word_id"),
            "target_word": matched.get("u") or matched.get("i") or target_word,
        }
        mapping_status = "mapped"
        prev_word_by_ayah[ayah] = word_pos
        if not target_word:
            target_word = normalize_arabic(matched.get("i") or "") or target_word
    elif ayah:
        mapping_status = "ayah_only"

    probe_for_t1 = old_text or text
    vlm_vs_shamela = shamela_compare(probe_for_t1, text_page, shamela)
    edit_status = "pristine" if not fixes else "normalized"

    # T1 auto-affirm: shamela match + no edits + mapped → review_status=affirmed
    # (no separate human step when T1 already holds)
    t1_ok = (
        vlm_vs_shamela == "match"
        and edit_status == "pristine"
        and mapping_status == "mapped"
    )
    review_status = "affirmed" if t1_ok else "pending"

    matched_anchor = None
    if label:
        matched_anchor = f"- {ayah} - {label}"
    elif ayah:
        matched_anchor = f"- {ayah}"

    return {
        "id": f"{BOOK_ID}:{surah_num}:{ayah}:{(position or {}).get('word') or 0}:{seq}",
        "book_id": BOOK_ID,
        "surah": surah_num,
        "ayah": ayah,
        "position": position,
        "target_word": target_word,
        "verdict_label": label,
        "verdict": verdict,
        "text": text,
        "old_text": old_text,
        "text_page": text_page,
        "evidence_type": "explicit_cataloged",
        "section": "wuquf",
        "mapping_method": "explicit_ayah_number",
        "matched_anchor": matched_anchor,
        "fixes": fixes,
        "trust": {
            "vlm_vs_shamela": vlm_vs_shamela,
            "edit_status": edit_status,
            "mapping_status": mapping_status,
            "review_status": review_status,
        },
    }


def attach_global_word_ids(
    by_sv: Dict[Tuple[int, int], List[Dict[str, Any]]],
    words_path: Path,
) -> None:
    """Annotate each word dict with _word_id = 1-based global index in quran-words.json."""
    data = json.loads(words_path.read_text(encoding="utf-8"))
    for idx, w in enumerate(data, start=1):
        key = (int(w["s"]), int(w["v"]))
        pos = int(w["p"])
        for item in by_sv.get(key, []):
            if int(item["p"]) == pos:
                item["_word_id"] = idx
                break


# ---------------------------------------------------------------------------
# Dual emit: flat corpus + nested mirror
# ---------------------------------------------------------------------------
def build_flat_corpus(entries: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    flat_entries = []
    for e in entries:
        pos = e.get("position") or {}
        flat_entries.append(
            {
                "id": e["id"],
                "bookId": e["book_id"],
                "kind": "waqf_ruling",
                "evidenceType": e.get("evidence_type"),
                "section": e.get("section"),
                "position": {
                    "surah": e.get("surah"),
                    "ayah": e.get("ayah"),
                    "word": pos.get("word"),
                    "wordId": pos.get("word_id"),
                    "targetWord": pos.get("target_word") or e.get("target_word"),
                },
                "verdict": e.get("verdict"),
                "verdictLabel": e.get("verdict_label"),
                "quote": e.get("text"),
                "old_text": e.get("old_text"),
                "fixes": e.get("fixes") or [],
                "trust": e.get("trust"),
                "text_page": e.get("text_page"),
                "mapping_method": e.get("mapping_method"),
                "matched_anchor": e.get("matched_anchor"),
                "summary": None,
                "hasWaqfTerm": True,
                "span": {
                    "rawFile": "Al-Sajawandi-Ilal-30007.json",
                    "charStart": None,
                    "charEnd": None,
                    "sectionMarker": None,
                    "page": e.get("text_page"),
                },
                "tahqeeq": None,
            }
        )
    return {
        "schemaVersion": 1,
        "book": {
            "id": "al-sajawandi",
            "title": meta["title"],
            "shortTitle": "السجاوندي",
            "author": meta["author"],
            "diedHijri": meta["died_hijri"],
            "role": "comparative_waqf",
            "rawFile": "Al-Sajawandi-Ilal.json",
            "modelLabel": "Gemini VLM",
            "entryCount": len(flat_entries),
            "surahCount": len({e.get("surah") for e in entries}),
        },
        "entries": flat_entries,
        "meta": {
            "part": meta.get("part"),
            "ayah_range": meta.get("ayah_range"),
            "page_range": meta.get("page_range"),
            "surah": meta.get("surah"),
            "surah_name": meta.get("surah_name"),
        },
    }


def build_nested_mirror(entries: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    surah_key = str(meta["surah"])
    ayahs: Dict[str, Dict[str, Any]] = {}

    for e in entries:
        a_key = str(e.get("ayah") or 0)
        if a_key not in ayahs:
            ayahs[a_key] = {"words": {}, "ayah_level": [], "llm_implicit": []}

        item = {
            "evidence_type": e.get("evidence_type"),
            "section": e.get("section"),
            "mapping_method": e.get("mapping_method"),
            "matched_anchor": e.get("matched_anchor"),
            "verdict": e.get("verdict"),
            "verdict_label": e.get("verdict_label"),
            "text": e.get("text"),
            "old_text": e.get("old_text"),
            "text_page": e.get("text_page"),
            "fixes": e.get("fixes") or [],
            "trust": e.get("trust"),
            "id": e.get("id"),
        }

        pos = e.get("position")
        if pos and pos.get("word") is not None:
            w_key = str(pos["word"])
            words = ayahs[a_key]["words"]
            if w_key not in words:
                words[w_key] = {
                    "word": pos["word"],
                    "word_id": pos.get("word_id"),
                    "target_word": e.get("target_word") or pos.get("target_word"),
                    "waqfs": [],
                }
            words[w_key]["waqfs"].append(item)
        else:
            ayahs[a_key]["ayah_level"].append(item)

    # sort ayah keys numerically in output via insertion order
    ordered = {k: ayahs[k] for k in sorted(ayahs.keys(), key=lambda x: int(x) if str(x).lstrip("-").isdigit() else 0)}

    return {
        **{k: meta[k] for k in ("book_id", "title", "author", "died_hijri", "source") if k in meta},
        "surah": meta["surah"],
        "surah_name": meta["surah_name"],
        "part": meta.get("part"),
        "ayah_range": meta.get("ayah_range"),
        "page_range": meta.get("page_range"),
        "surahs": {surah_key: ordered},
        "total_verses_in_part": len(ordered),
        "total_waqfs_in_part": len(entries),
    }


def write_companion_md(entries: List[Dict[str, Any]], meta: Dict[str, Any], path: Path) -> None:
    lines = [
        f"# علل الوقوف للسجاوندي - {meta.get('surah_name')}",
        f"**الصفحات:** {meta.get('page_range')} | **الآيات:** {meta.get('ayah_range')} | **العدد:** {len(entries)}",
        "",
        "| الرمز | الحكم المعياري |",
        "| :---: | :--- |",
        "| ط | تام |",
        "| م | لازم |",
        "| ج | جائز |",
        "| ز | جائز |",
        "| ص | حسن |",
        "| لا | لا يوقف |",
        "| ق | قيل فيه وقف |",
        "",
    ]
    cur = None
    for e in entries:
        if e.get("ayah") != cur:
            cur = e.get("ayah")
            lines.extend(["", f"### الآية {cur}"])
        t = e.get("trust") or {}
        lines.append(
            f"- `{e.get('target_word')}` | {e.get('verdict_label')}→{e.get('verdict')} | "
            f"map={t.get('mapping_status')} | shamela={t.get('vlm_vs_shamela')} | edit={t.get('edit_status')} | "
            f"review={t.get('review_status')}"
        )
        lines.append(f"  - {e.get('text')}")
        if e.get("fixes"):
            for fx in e["fixes"]:
                lines.append(f"  - fix `{fx.get('type')}` ({fx.get('basis')}): {fx.get('info')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def merge_part_into_book(
    part_flat: Dict[str, Any],
    part_nested: Dict[str, Any],
    book_flat_path: Path,
    book_nested_path: Path,
) -> None:
    """Merge a part's entries into whole-book flat + nested files."""
    if book_flat_path.exists():
        book_flat = json.loads(book_flat_path.read_text(encoding="utf-8"))
    else:
        book_flat = {"schemaVersion": 1, "book": part_flat["book"], "entries": [], "meta": {}}

    existing_ids = {e.get("id") for e in book_flat.get("entries") or []}
    for e in part_flat.get("entries") or []:
        if e.get("id") not in existing_ids:
            book_flat["entries"].append(e)
            existing_ids.add(e.get("id"))
    book_flat["book"]["entryCount"] = len(book_flat["entries"])
    book_flat_path.parent.mkdir(parents=True, exist_ok=True)
    book_flat_path.write_text(json.dumps(book_flat, ensure_ascii=False, indent=2), encoding="utf-8")

    if book_nested_path.exists():
        book_nested = json.loads(book_nested_path.read_text(encoding="utf-8"))
    else:
        book_nested = {
            **{k: part_nested[k] for k in ("book_id", "title", "author", "died_hijri", "source") if k in part_nested},
            "surahs": {},
        }
    for s_key, ayahs in (part_nested.get("surahs") or {}).items():
        book_nested.setdefault("surahs", {}).setdefault(s_key, {})
        for a_key, a_val in ayahs.items():
            book_nested["surahs"][s_key][a_key] = a_val
    book_nested_path.write_text(json.dumps(book_nested, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Merge] Updated {book_flat_path} and {book_nested_path}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def process_batch_raw_only(
    batch_pages: List[int],
    rendered_images: List[Path],
    use_grid: bool,
    backend: str,
    api_keys: List[str],
    base_url: Optional[str],
    model_name: str,
    raw_dir: Path,
    grid_dir: Path,
    rerun_vlm: bool,
    model_fallback: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Read immutable raw (or fetch once), parse to list of raw waqf dicts. Does not write raw after read."""
    raw_text = load_or_fetch_raw(
        batch_pages=batch_pages,
        rendered_images=rendered_images,
        use_grid=use_grid,
        backend=backend,
        api_keys=api_keys,
        base_url=base_url,
        model_name=model_name,
        raw_dir=raw_dir,
        grid_dir=grid_dir,
        rerun_vlm=rerun_vlm,
        model_fallback=model_fallback,
    )
    try:
        data = robust_json_loads(raw_text)
        return data.get("waqfs") or []
    except Exception as e:
        print(f"  [Parse Error] pages {batch_pages[0]}..{batch_pages[-1]}: {e}")
        return []


def run_surah_extraction(
    surah_num: int,
    surah_name: str,
    page_start: int,
    page_end: int,
    batch_size: int,
    use_grid: bool,
    backend: str,
    model_name: str,
    api_keys: List[str],
    base_url: Optional[str],
    pdf_path: Optional[Path],
    work_path: Path,
    quran_words_path: Path,
    quran_ayahs_path: Path,
    shamela_path: Optional[Path],
    rerun_vlm: bool = False,
    part: Optional[int] = None,
    ayah_start: Optional[int] = None,
    ayah_end: Optional[int] = None,
    output_nested: Optional[Path] = None,
    output_flat: Optional[Path] = None,
    output_md: Optional[Path] = None,
    output_extracted: Optional[Path] = None,
    merge_book: bool = True,
    model_fallback: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    images_dir = work_path / "rendered_pages"
    cache_dir = work_path / "cache"
    raw_dir = cache_dir / "raw"
    processed_dir = cache_dir / "processed"
    grid_dir = cache_dir / "grids"
    for d in (raw_dir, processed_dir, grid_dir, images_dir):
        d.mkdir(parents=True, exist_ok=True)

    pages_to_process = list(range(page_start, page_end + 1))
    coverage = index_raw_page_coverage(raw_dir)
    if rerun_vlm:
        missing_pages = pages_to_process[:]
    else:
        missing_pages = [p for p in pages_to_process if p not in coverage]

    model_chain = model_fallback or build_gemini_model_chain(model_name)
    print("\n" + "=" * 66)
    print(f"[*] Extraction {surah_name} (سورة {surah_num})" + (f" part {part}" if part else ""))
    print(f"    Pages {page_start}-{page_end} ({len(pages_to_process)} pages)")
    print(f"    Already in raw: {len(pages_to_process) - len(missing_pages)} | need VLM: {len(missing_pages)}")
    print(f"    Backend: {backend} | primary={model_name} | fallback={model_chain} | rerun_vlm={rerun_vlm}")
    print("=" * 66)

    search_dirs = [
        ANDROID_PAGES,
        Path("waqf-ibtida-web/public/data/pdf_pages/sajawandi"),
        Path("public/data/pdf_pages/sajawandi"),
        work_path / "rendered_pages",
    ]

    # Only render/fetch images for pages still missing raw
    if missing_pages:
    page_to_img = get_page_images(
            pages=missing_pages,
        search_dirs=search_dirs,
        pdf_path=str(pdf_path) if pdf_path else None,
        render_output_dir=images_dir,
            dpi=200,
        )
        for i in range(0, len(missing_pages), batch_size):
            batch_pages = missing_pages[i : i + batch_size]
        batch_imgs = [page_to_img[p] for p in batch_pages if p in page_to_img]
            try:
                batch_raw = process_batch_raw_only(
            batch_pages=batch_pages,
            rendered_images=batch_imgs,
            use_grid=use_grid,
            backend=backend,
            api_keys=api_keys,
            base_url=base_url,
            model_name=model_name,
                    raw_dir=raw_dir,
                    grid_dir=grid_dir,
                    rerun_vlm=rerun_vlm,
                    model_fallback=model_chain,
                )
            except Exception as e:
                # All keys/models exhausted (or hard failure) — stop the run.
                # Resume later will retry pages still missing from raw coverage.
                print(f"  [STOP] pages {batch_pages[0]}..{batch_pages[-1]}: {e}", flush=True)
                fail_log = processed_dir / "failed_batches.jsonl"
                with open(fail_log, "a", encoding="utf-8") as ff:
                    ff.write(
                        json.dumps(
                            {
                                "pages": batch_pages,
                                "surah": surah_num,
                                "part": part,
                                "error": str(e),
                                "at": datetime.now(timezone.utc).isoformat(),
                                "aborted": True,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                raise RuntimeError(
                    f"Aborting run after VLM failure on pages {batch_pages[0]}..{batch_pages[-1]}. "
                    f"Re-run later to resume missing pages. Cause: {e}"
                ) from e
            proc_file = processed_dir / f"batch_{batch_pages[0]}_{batch_pages[-1]}.json"
            proc_file.write_text(json.dumps(batch_raw, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(1.5)
    else:
        print("[*] All pages in this range already have immutable raw — skipping VLM.")

    print(f"[*] Loading Quran words from {quran_words_path}")
    by_sv = load_quran_words(quran_words_path)
    attach_global_word_ids(by_sv, quran_words_path)
    shamela = load_shamela_pages(shamela_path)
    print(f"[*] Shamela pages loaded: {len(shamela)}" + ("" if shamela else " (T1=no_shamela)"))

    # Compile from ALL raw files covering this page range (reuses part3 raw as-is)
    raw_waqfs = collect_raw_waqfs_for_page_range(raw_dir, page_start, page_end)

    # Normalize + map
    prev_word_by_ayah: Dict[int, int] = {}
    entries: List[Dict[str, Any]] = []
    seq = 0
    for rw in raw_waqfs:
        seq += 1
        entries.append(
            normalize_candidate(
                rw,
        surah_num=surah_num,
                seq=seq,
                by_sv=by_sv,
                prev_word_by_ayah=prev_word_by_ayah,
                shamela=shamela,
            )
        )

    if ayah_start is not None and ayah_end is not None:
        entries = [
            e
            for e in entries
            if e.get("ayah") and ayah_start <= int(e["ayah"]) <= ayah_end
        ]
    else:
        # Keep waqfs whose text_page falls in this part (raw files may span edges)
        entries = [
            e
            for e in entries
            if e.get("text_page") is None
            or (page_start <= int(e["text_page"]) <= page_end)
        ]

    entries.sort(
        key=lambda e: (
            int(e.get("ayah") or 0),
            int((e.get("position") or {}).get("word") or 0),
            int(e.get("text_page") or 0),
        )
    )

    ayah_nums = [int(e["ayah"]) for e in entries if e.get("ayah")]
    ayah_range = f"{min(ayah_nums)}-{max(ayah_nums)}" if ayah_nums else f"{ayah_start or '?'}-{ayah_end or '?'}"
    meta = {
        **BOOK_META,
        "surah": surah_num,
        "surah_name": surah_name,
        "part": part,
        "ayah_range": ayah_range,
        "page_range": f"{page_start}-{page_end}",
    }

    # Layer 2 extracted
    if output_extracted:
        extracted_path = output_extracted
    else:
        extracted_path = work_path / (
            f"sajawandi_surah{surah_num}_part{part}_extracted.json"
            if part
            else f"sajawandi_surah{surah_num}_extracted.json"
        )

    extracted_doc = {"schema": "sajawandi.extracted.v1", "meta": meta, "waqfs": entries}
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_path.write_text(json.dumps(extracted_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Done] Extracted layer: {extracted_path} ({len(entries)} waqfs)")

    nested = build_nested_mirror(entries, meta)
    flat = build_flat_corpus(entries, meta)

    nested_path = output_nested or Path(
        f"sajawandi_surah{surah_num}_part{part}.json" if part else f"sajawandi_surah{surah_num}.json"
    )
    flat_path = output_flat or Path(
        f"sajawandi_surah{surah_num}_part{part}.flat.json"
        if part
        else f"sajawandi_surah{surah_num}.flat.json"
    )
    md_path = output_md or nested_path.with_suffix(".md")

    if nested_path.exists():
        bak = nested_path.with_suffix(nested_path.suffix + ".bak")
        shutil.copy2(nested_path, bak)
        print(f"[Backup] {bak}")

    nested_path.write_text(json.dumps(nested, ensure_ascii=False, indent=2), encoding="utf-8")
    flat_path.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")
    write_companion_md(entries, meta, md_path)
    print(f"[Done] Nested mirror: {nested_path}")
    print(f"[Done] Flat corpus:   {flat_path}")
    print(f"[Done] Markdown:      {md_path}")

    mapped = sum(1 for e in entries if (e.get("trust") or {}).get("mapping_status") == "mapped")
    ayah_only = sum(1 for e in entries if (e.get("trust") or {}).get("mapping_status") == "ayah_only")
    pristine = sum(1 for e in entries if (e.get("trust") or {}).get("edit_status") == "pristine")
    t1_match = sum(1 for e in entries if (e.get("trust") or {}).get("vlm_vs_shamela") == "match")
    print(f"[Stats] mapped={mapped} ayah_only={ayah_only} pristine={pristine} shamela_match={t1_match}")

    if merge_book:
        book_flat = work_path / "al-sajawandi.flat.json"
        book_nested = work_path / "al-sajawandi.nested.json"
        merge_part_into_book(flat, nested, book_flat, book_nested)

    return entries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Al-Sajawandi VLM pipeline: immutable raw → extracted → flat+nested."
    )
    parser.add_argument("--surah", type=str, default=None, help="Surah number(s), e.g. '2' or '1,2,3'")
    parser.add_argument("--surah-num", type=int, default=None)
    parser.add_argument("--surah-name", type=str, default=None)
    parser.add_argument("--all-surahs", action="store_true", help="Run all surahs 1..114 from page map")
    parser.add_argument("--from-surah", type=int, default=None, help="Start surah (with --all-surahs or alone)")
    parser.add_argument("--to-surah", type=int, default=None, help="End surah inclusive")
    parser.add_argument("--part", type=int, default=None, help="Part number (batch slice); omit to auto-split")
    parser.add_argument(
        "--pages-per-part",
        type=int,
        default=42,
        help="Auto-split each surah into parts of this many pages (default 42). 0 = whole surah as one part",
    )
    parser.add_argument("--surah-map", type=str, default=str(DEFAULT_SURAH_MAP), help="sajawandi_surah_page_map.json")
    parser.add_argument("--start-page", type=int, default=None)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--ayah-start", type=int, default=None)
    parser.add_argument("--ayah-end", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=4, help="Pages per VLM API call (default 4)")
    parser.add_argument("--grid", action="store_true", default=True, help="Stitch batch pages into grid (default on)")
    parser.add_argument("--no-grid", action="store_true", help="Disable page grid")
    parser.add_argument("--backend", choices=["gemini", "openai"], default="gemini")
    # Gemini allowlist with automatic fallback chain (Gemini 3 Flash excluded)
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.6-flash",
        help=(
            "Primary Gemini model. On 429/5xx, falls back through: "
            + " → ".join(ALLOWED_GEMINI_MODELS)
        ),
    )
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--work-dir", type=str, default="./sajawandi_vlm_work")
    parser.add_argument("--pdf", default=str(Path(__file__).resolve().parent / "علل الوقوف - السجاوندي - ت العيدي 1-3 - KTB_0073685.pdf"))
    parser.add_argument("--quran-words", type=str, default=str(DEFAULT_QURAN_WORDS))
    parser.add_argument("--quran-ayahs", type=str, default=str(DEFAULT_QURAN_AYAHS))
    parser.add_argument("--shamela", type=str, default=str(DEFAULT_SHAMELA), help="Shamela JSON for T1 only")
    parser.add_argument("--no-shamela", action="store_true", help="Disable Shamela T1 compare")
    parser.add_argument("--rerun-vlm", action="store_true", default=False, help="Replace immutable raw (off by default)")
    parser.add_argument("--output-json", type=str, default=None, help="Nested mirror output path")
    parser.add_argument("--output-flat", type=str, default=None, help="Flat corpus output path")
    parser.add_argument("--output-md", type=str, default=None)
    parser.add_argument("--output-extracted", type=str, default=None)
    parser.add_argument("--no-merge-book", action="store_true", help="Skip merging into whole-book files")

    args = parser.parse_args()

    if args.backend == "gemini" and args.model not in ALLOWED_GEMINI_MODELS:
        parser.error(
            f"Model '{args.model}' not allowed. Use one of: {', '.join(ALLOWED_GEMINI_MODELS)}"
        )
    model_chain = build_gemini_model_chain(args.model)

    # Prefer explicit CLI / env (supports comma-separated multi-key rotation)
    raw_key = args.api_key or os.environ.get(
        "GEMINI_API_KEYS" if args.backend == "gemini" else "OPENAI_API_KEY"
    ) or os.environ.get("GEMINI_API_KEY" if args.backend == "gemini" else "OPENAI_API_KEY")

    # Also pull from WaqfWIbtida .env if present
    env_candidates = [
        Path(__file__).resolve().parent / ".env",
        Path(r"C:\Users\Khaled\AndroidStudioProjects\WaqfWIbtida\waqf-ibtida-web\.env"),
    ]
    env_keys: List[str] = []
    for env_path in env_candidates:
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() in ("GEMINI_API_KEY", "GEMINI_API_KEYS") and v.strip():
                    env_keys.extend([x.strip() for x in v.split(",") if x.strip()])
        except Exception:
            pass

    # Keys only from --api-key / GEMINI_API_KEY(S) / .env — never hardcode secrets
    default_keys: List[str] = []

    if raw_key:
        api_keys = [k.strip() for k in raw_key.split(",") if k.strip()]
    elif args.backend == "gemini":
        # dedupe, preserve order: env keys first
        seen = set()
        api_keys = []
        for k in env_keys + default_keys:
            if k and k not in seen:
                seen.add(k)
                api_keys.append(k)
    else:
        api_keys = ["local"]

    if args.backend == "gemini":
        print(f"[*] Gemini API keys in rotation: {len(api_keys)}")

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        for cand in [
            Path(__file__).resolve().parent / "علل الوقوف - السجاوندي - ت العيدي 1-3 - KTB_0073685.pdf",
            Path(r"C:\Users\Khaled\Downloads\علل الوقوف - السجاوندي - ت العيدي 1-3 - KTB_0073685-1-600.pdf"),
        ]:
            if cand.exists():
                pdf_path = cand
                break
        else:
            pdf_path = None

    work_path = Path(args.work_dir)
    quran_words = Path(args.quran_words)
    quran_ayahs = Path(args.quran_ayahs)
    shamela_path = None if args.no_shamela else Path(args.shamela)
    surah_presets = load_surah_presets(Path(args.surah_map))
    use_grid = False if args.no_grid else bool(args.grid)

    # Resolve which surahs to run
    if args.all_surahs or args.from_surah or args.to_surah:
        lo = args.from_surah or 1
        hi = args.to_surah or 114
        surah_list = [n for n in range(lo, hi + 1) if n in surah_presets]
    elif args.surah:
        surah_list = [int(s.strip()) for s in args.surah.split(",") if s.strip()]
    elif args.surah_num:
        surah_list = [args.surah_num]
    elif args.part:
        surah_list = [2]
    else:
        surah_list = [2]

    print(f"[*] Surah page map: {args.surah_map} ({len(surah_presets)} surahs)")
    print(f"[*] Queue: {surah_list[0]}..{surah_list[-1]} ({len(surah_list)} surahs)")

    for s_num in surah_list:
        preset = surah_presets.get(s_num, {})
        s_name = args.surah_name or preset.get("name") or f"سورة رقم {s_num}"
        surah_start = preset.get("start")
        surah_end = preset.get("end")

        # Explicit single part (manual override or PART_PRESETS)
        if args.part is not None and len(surah_list) == 1 and not args.start_page:
            part_preset = PART_PRESETS.get((s_num, args.part))
            if part_preset:
                jobs = [
                    (
                        args.part,
                        part_preset["start"],
                        part_preset["end"],
                        part_preset.get("ayah_start"),
                        part_preset.get("ayah_end"),
                        part_preset.get("name") or s_name,
                    )
                ]
            elif surah_start and surah_end:
                auto = split_surah_into_parts(int(surah_start), int(surah_end), args.pages_per_part)
                match = [x for x in auto if x[0] == args.part]
                if not match:
                    print(f"Error: part {args.part} out of range for surah {s_num} ({len(auto)} parts)")
            continue
                pn, ps, pe = match[0]
                jobs = [(pn, ps, pe, args.ayah_start, args.ayah_end, s_name)]
            else:
                print(f"Error: no page range for surah {s_num} part {args.part}")
                continue
        elif args.start_page and args.end_page and len(surah_list) == 1:
            jobs = [
                (
                    args.part or 1,
                    args.start_page,
                    args.end_page,
                    args.ayah_start,
                    args.ayah_end,
                    s_name,
                )
            ]
        else:
            if not surah_start or not surah_end:
                print(f"Error: Unknown page range for surah {s_num}. Check --surah-map.")
                continue
            auto = split_surah_into_parts(int(surah_start), int(surah_end), args.pages_per_part)
            jobs = [(pn, ps, pe, None, None, s_name) for pn, ps, pe in auto]

        for part, p_start, p_end, a_start, a_end, job_name in jobs:
            single = len(surah_list) == 1 and len(jobs) == 1
            out_nested = Path(args.output_json) if args.output_json and single else None
            if out_nested is None and part == 3 and s_num == 2:
                out_nested = Path(__file__).resolve().parent / "sajawandi_surah2_part3.json"
            out_flat = Path(args.output_flat) if args.output_flat and single else None
            out_md = Path(args.output_md) if args.output_md and single else None
            out_ex = Path(args.output_extracted) if args.output_extracted and single else None

            print(f"\n>>> Surah {s_num} part {part}: pages {p_start}-{p_end}")
        run_surah_extraction(
            surah_num=s_num,
                surah_name=job_name,
                page_start=int(p_start),
                page_end=int(p_end),
            batch_size=args.batch_size,
                use_grid=use_grid,
            backend=args.backend,
            model_name=args.model,
            api_keys=api_keys,
            base_url=args.base_url,
            pdf_path=pdf_path,
            work_path=work_path,
                quran_words_path=quran_words,
                quran_ayahs_path=quran_ayahs,
                shamela_path=shamela_path,
                rerun_vlm=args.rerun_vlm,
                part=part,
                ayah_start=a_start,
                ayah_end=a_end,
                output_nested=out_nested,
                output_flat=out_flat,
                output_md=out_md,
                output_extracted=out_ex,
                merge_book=not args.no_merge_book,
                model_fallback=model_chain,
            )

    print("\n[*] All requested runs completed.")


if __name__ == "__main__":
    main()
