#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schema enums and constants for Al-Sajawandi Waqf extraction.
Directly aligned with 'علل الوقوف - السجاوندي - ت العيدي 1-3 - KTB_0073685-1-600.pdf'.
"""

from enum import Enum
from typing import Optional, Dict, Any

class WaqfVerdict(str, Enum):
    """الحكم المعياري الموحد للوقف وفق المنظومة الإسلامية المعتمدة."""
    TAM = "تام"
    KAFI = "كاف"
    HASAN = "حسن"
    JAIZ = "جائز"
    LAZIM = "لازم"
    LA_YUQAF = "لا يوقف"
    QABIH = "قبيح"
    QILA_FIHI_WAQF = "قيل فيه وقف"

class WaqfVerdictLabel(str, Enum):
    """الرمز الحرفي المعتمد عند السجاوندي في متن كتابه."""
    TA = "ط"      # مطلق
    MIM = "م"     # لازم
    JIM = "ج"     # جائز
    ZAY = "ز"     # مجوز لوجه
    SAD = "ص"     # مرخص ضرورة
    LA = "لا"     # لا يوقف
    QAF = "ق"     # قيل فيه وقف (مواضع استثنائية)

class FixType(str, Enum):
    """التصنيف المعياري المقيد لأنواع تصويبات الخلل الطباعي والهيكلي في المطبوع."""
    MISSING_DELIMITER = "missing_delimiter"       # سقوط الفاصل الشرطي بين الرقم والرمز (مثل: 16 ص -> - 16 - ص)
    ORTHOGRAPHY = "orthography"                   # التصاق حروف أو كلمات تقتضي الفصل (مثل: لاريب -> لا ريب)
    PAGE_SPLIT = "page_split"                     # انقطاع القوس بين صفحتين أو سطرين متعاقبين
    MISSING_SYMBOL = "missing_symbol"             # سقوط رمز الوقف الحرفي من المطبوع
    AYAH_NUMBER_CORRECTION = "ayah_number_correction"  # خطأ في رقم الآية المطبوع
    MALFORMED_BRACKET = "malformed_bracket"       # اضطراب في حاصرتي القوس القرآني

VERDICT_MAPPING: Dict[WaqfVerdictLabel, WaqfVerdict] = {
    WaqfVerdictLabel.TA: WaqfVerdict.TAM,  # مطلق → تام
    WaqfVerdictLabel.MIM: WaqfVerdict.LAZIM,
    WaqfVerdictLabel.JIM: WaqfVerdict.JAIZ,
    WaqfVerdictLabel.ZAY: WaqfVerdict.JAIZ,
    WaqfVerdictLabel.SAD: WaqfVerdict.HASAN,
    WaqfVerdictLabel.LA: WaqfVerdict.LA_YUQAF,
    WaqfVerdictLabel.QAF: WaqfVerdict.QILA_FIHI_WAQF,
}