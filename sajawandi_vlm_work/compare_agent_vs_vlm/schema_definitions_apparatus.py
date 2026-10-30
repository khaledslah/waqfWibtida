#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apparatus raw enums — pairs with raw_waqf_apparatus.schema.json.
Numbered closing-bracket refs → matching margin → per-scholar opinions.
"""

from enum import Enum
from typing import Dict, List, Optional, TypedDict


class WaqfVerdictLabel(str, Enum):
    TA = "ط"
    MIM = "م"
    JIM = "ج"
    ZAY = "ز"
    SAD = "ص"
    LA = "لا"
    QAF = "ق"


class WaqfVerdict(str, Enum):
    TAM = "تام"
    LAZIM = "لازم"
    JAIZ = "جائز"
    HASAN = "حسن"
    LA_YUQAF = "لا يوقف"
    QILA_FIHI_WAQF = "قيل فيه وقف"


VERDICT_MAPPING: Dict[WaqfVerdictLabel, WaqfVerdict] = {
    WaqfVerdictLabel.TA: WaqfVerdict.TAM,
    WaqfVerdictLabel.MIM: WaqfVerdict.LAZIM,
    WaqfVerdictLabel.JIM: WaqfVerdict.JAIZ,
    WaqfVerdictLabel.ZAY: WaqfVerdict.JAIZ,
    WaqfVerdictLabel.SAD: WaqfVerdict.HASAN,
    WaqfVerdictLabel.LA: WaqfVerdict.LA_YUQAF,
    WaqfVerdictLabel.QAF: WaqfVerdict.QILA_FIHI_WAQF,
}


class FixType(str, Enum):
    PAGE_SPLIT = "page_split"
    MISSING_DELIMITER = "missing_delimiter"
    MISSING_SYMBOL = "missing_symbol"
    ORTHOGRAPHY = "orthography"
    AYAH_NUMBER_CORRECTION = "ayah_number_correction"
    MALFORMED_BRACKET = "malformed_bracket"


class FixBasis(str, Enum):
    PAGE_PROSE = "page_prose"
    EDITOR_POLICY = "editor_policy"


class Scholar(str, Enum):
    """Canonical scholar ids for opinions[].scholar (exact JSON string)."""
    IBN_AL_ANBARI = "ابن الأنباري"
    NAHHAS = "النحاس"
    DANI = "الداني"
    ASHMUNI = "الأشموني"
    AKHFASH = "الأخفش"
    KISAI = "الكسائي"
    MAKKI = "مكي"
    UKBARI = "العكبري"
    ANSARI = "الأنصاري"
    TABARI = "الطبري"
    IBN_ATIYYA = "ابن عطية"
    UNKNOWN = "unknown"


# Prompt/VLM: map printed variants → Scholar value; else unknown.
SCHOLAR_ALIAS_HINTS: Dict[Scholar, List[str]] = {
    Scholar.IBN_AL_ANBARI: ["أبي البركات ابن الأنباري", "ابن الانباري", "الأنباري"],
    Scholar.NAHHAS: ["أبي جعفر النحاس", "النحّاس"],
    Scholar.DANI: ["أبي عمرو الداني", "أبو عمرو الداني"],
    Scholar.ASHMUNI: ["الاشموني", "أحمد بن محمد الأشموني"],
    Scholar.AKHFASH: ["الأخفش الأوسط", "الاخفش"],
    Scholar.MAKKI: ["مكي بن أبي طالب", "مكي القيسي"],
    Scholar.UKBARI: ["أبي البقاء العكبري", "العكبرى"],
    Scholar.ANSARI: ["زكريا الأنصاري", "شيخ الإسلام الأنصاري"],
    Scholar.TABARI: ["محمد بن جرير الطبري", "ابن جرير"],
    Scholar.IBN_ATIYYA: ["القاضي ابن عطية", "أبي محمد ابن عطية"],
}


class ScholarOpinion(TypedDict, total=False):
    scholar: str  # Scholar value if known; else name as printed; "unknown" only if no name
    verdict: str  # final word: حسن / كاف / تام / …
    comment: Optional[str]
    book: Optional[str]
    book_ref: Optional[str]


class SymbolWitness(TypedDict, total=False):
    verdict_label: str
    basis: str  # page_prose
    witness: Optional[str]
    info: Optional[str]


class Continuation(TypedDict):
    status: str  # read | missing
    page: Optional[int]


class SuggestedWaqf(TypedDict):
    target_word: str
    trigger: str  # scholars_disagree | meaning_change
    reason: str
    scholars: List[str]


class SuggestedIbtida(TypedDict):
    start_word: str
    trigger: str  # scholars_disagree | meaning_change
    reason: str
    scholars: List[str]


class Suggested(TypedDict):
    """Pass 3 only. AI-inferred; never edits pass 1/2 fields."""
    basis: str  # ai_inferred
    waqf: List[SuggestedWaqf]
    ibtida: List[SuggestedIbtida]


class ApparatusNote(TypedDict, total=False):
    margin_ref: int
    text_page: int
    raw_text: Optional[str]
    continuation: Optional[Continuation]
    symbol_witness: Optional[SymbolWitness]
    opinions: List[ScholarOpinion]
    suggested: Optional[Suggested]  # pass 3 only


class ApparatusWaqf(TypedDict, total=False):
    ayah: int
    target_word: str
    verdict_label: Optional[str]
    verdict: Optional[str]
    margin_ref: Optional[int]
    text: str
    text_page: int
    old_text: Optional[str]
    fixes: List[dict]
    apparatus: List[ApparatusNote]
