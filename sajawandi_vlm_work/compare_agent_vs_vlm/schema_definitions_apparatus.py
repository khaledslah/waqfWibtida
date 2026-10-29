#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEW file — apparatus/margin-aware trial enums only.
Does not modify schema_definitions.py or the grilled raw schema.
"""

from enum import Enum
from typing import Dict

# Re-declare grilled labels/verdicts here so this module stays standalone.
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


class VerdictStatus(str, Enum):
    """Whether the Sajawandi letter/ruling is settled for this waqf row."""
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    CONTESTED = "contested"


class VerdictResolutionBasis(str, Enum):
    """How verdict_label was chosen (or why not)."""
    MATN_SYMBOL = "matn_symbol"
    PAGE_PROSE = "page_prose"
    DUAL_MATN_SYMBOL = "dual_matn_symbol"
    UNRESOLVED = "unresolved"


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


class ApparatusSourceKind(str, Enum):
    MARGIN = "margin"
    MATN_ASIDE = "matn_aside"
    HEADER = "header"


class ApparatusNoteKind(str, Enum):
    SYMBOL_WITNESS = "symbol_witness"
    SCHOLAR_OPINION = "scholar_opinion"
    WORK_CITATION = "work_citation"
    VARIANT = "variant"
    OTHER = "other"


class KnownScholarOrWork(str, Enum):
    NAHHAS = "النحاس"
    DANI = "الداني"
    AKHFASH = "الأخفش"
    KISAI = "الكسائي"
    MAKKI = "مكي"
    IBN_AL_ANBARI = "ابن الأنباري"
    UKBARI = "العكبري"
    NUSKHA_ALIF = "نسخة أ"
    NUSKHA_BA = "نسخة ب"
    UNKNOWN = "unknown"
